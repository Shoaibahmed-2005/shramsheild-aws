"""Live check: build today's plan for all four demo sites against Open-Meteo.

Usage: python scripts/verify_live.py [--date YYYY-MM-DD]
Exits 1 if any site fails to fetch, build or validate.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shramshield_core import weather  # noqa: E402
from shramshield_core.contract import validate_plan  # noqa: E402
from shramshield_core.plan import build_plan, india_today  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SITES_FILE = REPO_ROOT / "shared" / "fixtures" / "sites.json"


def check_site(site: dict, date_str: str) -> tuple[bool, str]:
    """Fetch, build and validate one site. Returns (ok, one-line report)."""
    started = time.perf_counter()
    label = f"{site['site_id']:<7}"
    try:
        response = weather.fetch_forecast(site["lat"], site["lon"])
        rows = weather.rows_for_date(weather.parse_hourly(response), date_str)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = build_plan(site, rows, date_str, generated_at)
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        elapsed = time.perf_counter() - started
        return False, f"FAIL  {label} {type(exc).__name__}: {exc}  ({elapsed:.2f} s)"

    errors = validate_plan(plan)
    elapsed = time.perf_counter() - started
    summary = plan["summary"]
    fallback = plan["source"].get("simple_fallback_hours", 0)
    unknown = sum(1 for hour in plan["hours"] if hour["level"] == "UNKNOWN")

    detail = (
        f"{label} peak WBGT {str(summary['peak_wbgt_c']):>5} C at "
        f"{str(summary['peak_hour']):>2}:00  worst {summary['worst_level']:<7} "
        f"fallback hours {fallback}  unknown hours {unknown}  ({elapsed:.2f} s)"
    )
    if errors:
        return False, f"FAIL  {detail}\n        {len(errors)} validation error(s): {errors[:3]}"
    return True, f"OK    {detail}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", dest="date", default=None, help="default today in India")
    args = parser.parse_args(argv[1:])

    date_str = args.date or india_today()
    sites = json.loads(SITES_FILE.read_text(encoding="utf-8"))["sites"]

    print(f"Live verification for {date_str} (India time), {len(sites)} sites")
    print()

    failures = 0
    for site in sites:
        ok, report = check_site(site, date_str)
        print(f"  {report}")
        failures += not ok

    print()
    if failures:
        print(f"{failures} of {len(sites)} sites FAILED")
        return 1
    print(f"all {len(sites)} sites OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
