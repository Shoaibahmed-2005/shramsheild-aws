#!/usr/bin/env python3
"""End-to-end smoke verification for the deployed ShramShield HTTP API.

Usage:
  python backend/scripts/smoke.py --api https://... [--key SECRET]
"""

import argparse
import json
import os
from pathlib import Path
import random
import string
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

# Ensure backend/src is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
src_dir = backend_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    from shramshield_core.contract import DISCLAIMER, validate_plan
except ImportError:
    from src.shramshield_core.contract import DISCLAIMER, validate_plan


def request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, str], Any]:
    """Perform HTTP request, return (status_code, headers_dict, parsed_json_or_text)."""
    hdrs = headers.copy() if headers else {}
    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            raw = resp.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except Exception:
                body = raw
            return status, resp_headers, body
    except urllib.error.HTTPError as exc:
        resp_headers = {k.lower(): v for k, v in exc.headers.items()}
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except Exception:
            body = raw
        return exc.code, resp_headers, body


def run_check(name: str, check_fn) -> bool:
    try:
        ok, msg = check_fn()
        if ok:
            print(f"  [PASS] {name} - {msg}")
            return True
        else:
            print(f"  [FAIL] {name} - {msg}")
            return False
    except Exception as exc:
        print(f"  [FAIL] {name} - Exception: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test ShramShield deployed API")
    parser.add_argument("--api", required=True, help="Base API URL without trailing slash")
    parser.add_argument("--key", default=None, help="Demo key (default from DEMO_KEY env var)")
    args = parser.parse_args()

    api_url = args.api.rstrip("/")
    demo_key = args.key or os.environ.get("DEMO_KEY", "")

    print(f"\n=======================================================")
    print(f"Starting ShramShield Smoke Tests against: {api_url}")
    print(f"=======================================================\n")

    results = []

    # 1. Health check
    def check_health():
        status, _, body = request(f"{api_url}/health")
        if status != 200:
            return False, f"Expected 200, got {status}"
        if not body.get("ok") or body.get("service") != "shramshield":
            return False, f"Unexpected body: {body}"
        if not body.get("thermofeel"):
            return False, f"thermofeel version is null or missing: {body}"
        return True, f"HTTP 200, thermofeel: {body.get('thermofeel')}"

    results.append(run_check("1. GET /health", check_health))

    # 2. Sites list check
    def check_sites():
        status, _, body = request(f"{api_url}/sites")
        if status != 200:
            return False, f"Expected 200, got {status}"
        sites = body.get("sites", [])
        if len(sites) < 4:
            return False, f"Expected at least 4 sites, got {len(sites)}"
        site_ids = [s["site_id"] for s in sites]
        return True, f"HTTP 200, {len(sites)} sites found: {site_ids[:4]}"

    results.append(run_check("2. GET /sites (at least 4 sites)", check_sites))

    # 3. Plan for chn-01 check
    plan_timing = 0.0

    def check_plan_chennai():
        nonlocal plan_timing
        start_time = time.time()
        status, headers, body = request(f"{api_url}/sites/chn-01/plan")
        plan_timing = time.time() - start_time
        if status != 200:
            return False, f"Expected 200, got {status}: {body}"
        hours = body.get("hours", [])
        if len(hours) != 24:
            return False, f"Expected 24 hours, got {len(hours)}"
        if body.get("disclaimer") != DISCLAIMER:
            return False, "Disclaimer text does not match contract exactly"
        errors = validate_plan(body)
        if errors:
            return False, f"Plan contract validation failed: {errors[:2]}"
        return True, f"HTTP 200 ({plan_timing:.2f}s), 24 valid hours, exact disclaimer, x-cache: {headers.get('x-cache')}"

    results.append(run_check("3. GET /sites/chn-01/plan (fresh calculation)", check_plan_chennai))

    # 4. Plan cache HIT check
    def check_plan_cache_hit():
        start_time = time.time()
        status, headers, body = request(f"{api_url}/sites/chn-01/plan")
        duration = time.time() - start_time
        if status != 200:
            return False, f"Expected 200, got {status}"
        cache_header = headers.get("x-cache", "")
        if cache_header != "HIT":
            return False, f"Expected x-cache header 'HIT', got '{cache_header}'"
        return True, f"HTTP 200 ({duration:.2f}s), x-cache: {cache_header}"

    results.append(run_check("4. GET /sites/chn-01/plan (cache HIT)", check_plan_cache_hit))

    # 5. Bad date check
    def check_bad_date():
        status, _, body = request(f"{api_url}/sites/chn-01/plan?date=2020-01-01")
        if status != 400:
            return False, f"Expected 400 bad_request, got {status}: {body}"
        err = body.get("error", {})
        if err.get("code") != "bad_request":
            return False, f"Expected error code 'bad_request', got {err.get('code')}"
        return True, f"HTTP 400 bad_request as expected: {err.get('message')}"

    results.append(run_check("5. GET /sites/chn-01/plan?date=2020-01-01 (bad date)", check_bad_date))

    # 6. POST /sites without key check
    test_site_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    test_site_id = f"test-smoke-{test_site_suffix}"
    test_site_payload = {
        "site_id": test_site_id,
        "name": f"Smoke Test Site {test_site_suffix}",
        "lat": 13.085,
        "lon": 80.2101,
        "workload": "moderate",
        "acclimatized": True,
        "work_start_hour": 7,
        "work_end_hour": 18,
        "language": "hi",
        "supervisor": {"name": "Supervisor", "telegram_chat_id": None},
        "backup": {"name": "Backup", "telegram_chat_id": None},
        "ack_timeout_seconds": 900,
    }

    def check_post_without_key():
        status, _, body = request(f"{api_url}/sites", method="POST", data=test_site_payload)
        if status != 401:
            return False, f"Expected 401 unauthorized, got {status}: {body}"
        return True, f"HTTP 401 unauthorized as expected"

    results.append(run_check("6. POST /sites without x-demo-key", check_post_without_key))

    # 7. POST /sites with valid key check
    if not demo_key:
        print("  [WARN] Skipping tests 7 & 8: No DEMO_KEY provided via --key or DEMO_KEY env var.")
    else:

        def check_post_with_key():
            status, _, body = request(
                f"{api_url}/sites",
                method="POST",
                headers={"x-demo-key": demo_key},
                data=test_site_payload,
            )
            if status != 201:
                return False, f"Expected 201 created, got {status}: {body}"
            if body.get("site_id") != test_site_id:
                return False, f"Returned site_id mismatch: {body.get('site_id')}"
            return True, f"HTTP 201 created. (Note: created test site '{test_site_id}' remains in table)"

        results.append(run_check("7. POST /sites with valid x-demo-key", check_post_with_key))

        # 8. Duplicate POST check
        def check_post_duplicate():
            status, _, body = request(
                f"{api_url}/sites",
                method="POST",
                headers={"x-demo-key": demo_key},
                data=test_site_payload,
            )
            if status != 409:
                return False, f"Expected 409 conflict for duplicate, got {status}: {body}"
            err = body.get("error", {})
            if err.get("code") != "conflict":
                return False, f"Expected error code 'conflict', got {err.get('code')}"
            return True, f"HTTP 409 conflict as expected: {err.get('message')}"

        results.append(run_check("8. POST /sites duplicate conflict check", check_post_duplicate))

    total = len(results)
    passed = sum(1 for r in results if r)
    failed = total - passed

    print(f"\n=======================================================")
    print(f"Smoke Test Summary: {passed}/{total} passed, {failed} failed.")
    print(f"=======================================================\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
