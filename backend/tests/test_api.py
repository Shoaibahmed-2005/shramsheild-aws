"""Tests for ShramShield HTTP API, DynamoDB integration, and plan routes."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

import pytest

# Ensure backend/src is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
src_dir = backend_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import api
from common import db
from common.http import json_response
from shramshield_core.weather import WeatherError

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))


class FakeDynamoDBTable:
    """In-memory mock DynamoDB table matching single-table contract 3.10."""

    def __init__(self, name: str = "test-shramshield-table") -> None:
        self.name = name
        self.items: Dict[tuple, Dict[str, Any]] = {}

    def get_item(self, Key: Dict[str, Any]) -> Dict[str, Any]:
        pk = Key.get("PK")
        sk = Key.get("SK")
        item = self.items.get((pk, sk))
        if item:
            return {"Item": item.copy()}
        return {}

    def put_item(self, Item: Dict[str, Any]) -> Dict[str, Any]:
        pk = Item.get("PK")
        sk = Item.get("SK")
        self.items[(pk, sk)] = Item.copy()
        return {}

    def scan(self, FilterExpression: Any = None, ExclusiveStartKey: Any = None) -> Dict[str, Any]:
        res = []
        for (pk, sk), item in self.items.items():
            if str(pk).startswith("SITE#") and sk == "META":
                res.append(item.copy())
        return {"Items": res}

    def update_item(
        self,
        Key: Dict[str, Any],
        UpdateExpression: str,
        ConditionExpression: Optional[str] = None,
        ExpressionAttributeNames: Optional[Dict[str, str]] = None,
        ExpressionAttributeValues: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pk = Key.get("PK")
        sk = Key.get("SK")
        item = self.items.get((pk, sk))
        if not item:
            item = {"PK": pk, "SK": sk}
            self.items[(pk, sk)] = item

        vals = ExpressionAttributeValues or {}

        # Evaluate condition expression
        if ConditionExpression:
            current_status = item.get("status")
            if ":allowed_0" in vals:
                allowed = [v for k, v in vals.items() if k.startswith(":allowed_")]
                if current_status not in allowed:
                    from botocore.exceptions import ClientError
                    raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
            elif ":ack" in vals:
                if current_status in ("ACKNOWLEDGED", "UNACKNOWLEDGED", "FAILED"):
                    from botocore.exceptions import ClientError
                    raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")

        # Apply updates
        if ":d" in vals:
            item["data"] = vals[":d"]
        if ":s" in vals:
            item["status"] = vals[":s"]
        if ":ev" in vals:
            if "data" in item:
                item["data"]["events"] = vals[":ev"]

        return {"Attributes": item.copy()}


def make_event(
    method: str = "GET",
    path: str = "/health",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    query_params: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Helper to construct an API Gateway Payload 2.0 test event."""
    hdrs = {}
    if headers:
        hdrs = {str(k).lower(): str(v) for k, v in headers.items()}

    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": hdrs,
        "queryStringParameters": query_params or {},
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            }
        },
        "body": body,
        "isBase64Encoded": False,
    }


def sample_site(**overrides: Any) -> Dict[str, Any]:
    base = {
        "site_id": "chn-01",
        "name": "Chennai demo site",
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
    base.update(overrides)
    return base


def fake_open_meteo_forecast(lat: float, lon: float) -> Dict[str, Any]:
    """Fake Open-Meteo forecast with 24 hours of valid data."""
    today = datetime.now(INDIA_TZ).date()
    times = []
    for day_offset in range(-1, 3):
        d = today + timedelta(days=day_offset)
        for h in range(24):
            times.append(f"{d.isoformat()}T{h:02d}:00")

    n = len(times)
    return {
        "hourly": {
            "time": times,
            "temperature_2m": [33.5] * n,
            "relative_humidity_2m": [60] * n,
            "surface_pressure": [1010.0] * n,
            "wind_speed_10m": [2.5] * n,
            "shortwave_radiation": [600.0] * n,
            "direct_radiation": [400.0] * n,
        }
    }


@pytest.fixture
def mock_dynamodb(monkeypatch):
    """Set up a mock DynamoDB table for testing."""
    table = FakeDynamoDBTable("test-shramshield-table")
    monkeypatch.setenv("TABLE_NAME", "test-shramshield-table")
    monkeypatch.setenv("DEMO_KEY", "test-secret-key-12345")
    monkeypatch.setenv("WEATHER_CACHE_SECONDS", "1200")
    api.set_table(table)
    yield table
    api.set_table(None)


# ---------------------------------------------------------------------------
# db.py Tests
# ---------------------------------------------------------------------------


def test_to_ddb_and_from_ddb():
    """to_ddb converts floats to Decimal; from_ddb converts Decimal back to int/float."""
    obj = {
        "int_val": 42,
        "float_val": 32.5,
        "integral_float": 32.0,
        "list_val": [1, 2.5, {"nested_float": 10.1}],
        "str_val": "test",
        "bool_val": True,
        "none_val": None,
    }

    ddb_converted = db.to_ddb(obj)
    assert isinstance(ddb_converted["float_val"], Decimal)
    assert isinstance(ddb_converted["integral_float"], Decimal)
    assert isinstance(ddb_converted["list_val"][1], Decimal)

    recovered = db.from_ddb(ddb_converted)
    assert recovered["int_val"] == 42
    assert isinstance(recovered["int_val"], int)
    assert recovered["float_val"] == 32.5
    assert isinstance(recovered["float_val"], float)
    assert recovered["list_val"][1] == 2.5
    assert recovered["str_val"] == "test"
    assert recovered["bool_val"] is True
    assert recovered["none_val"] is None


def test_db_sites_crud(mock_dynamodb):
    """Test get_site, put_site, and list_sites."""
    table = mock_dynamodb

    site_a = sample_site(site_id="site-b", name="Site B")
    site_b = sample_site(site_id="site-a", name="Site A")

    db.put_site(table, site_a)
    db.put_site(table, site_b)

    # get_site
    fetched = db.get_site(table, "site-a")
    assert fetched is not None
    assert fetched["name"] == "Site A"
    assert fetched["lat"] == 13.085

    assert db.get_site(table, "nonexistent") is None

    # list_sites should be sorted by site_id
    sites = db.list_sites(table)
    assert len(sites) == 2
    assert sites[0]["site_id"] == "site-a"
    assert sites[1]["site_id"] == "site-b"


def test_db_plan_cache_ttl(mock_dynamodb):
    """Cached plan returns plan when fresh, None when TTL is expired."""
    table = mock_dynamodb
    plan_data = {"plan_id": "chn-01_2026-10-11", "peak_wbgt": 32.5}

    # Fresh item
    db.put_cached_plan(table, "chn-01", "2026-10-11", plan_data, ttl_seconds=1200)
    cached = db.get_cached_plan(table, "chn-01", "2026-10-11")
    assert cached is not None
    assert cached["peak_wbgt"] == 32.5

    # Expired item (ttl in the past)
    db.put_cached_plan(table, "chn-01", "2026-10-11", plan_data, ttl_seconds=-60)
    assert db.get_cached_plan(table, "chn-01", "2026-10-11") is None


# ---------------------------------------------------------------------------
# API Handler Tests
# ---------------------------------------------------------------------------


def test_health_check():
    """GET /health returns 200 and required contract fields."""
    resp = api.handler(make_event("GET", "/health"))
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["service"] == "shramshield"
    # /health reports the bundled core version, so a deploy is verifiable from outside.
    from shramshield_core import __version__ as core_version

    assert body["version"] == core_version
    assert "thermofeel" in body


def test_get_sites_and_get_site_by_id(mock_dynamodb):
    """GET /sites returns site list, GET /sites/{id} returns site or 404."""
    db.put_site(mock_dynamodb, sample_site(site_id="chn-01", name="Chennai"))

    # GET /sites
    resp = api.handler(make_event("GET", "/sites"))
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])
    assert "sites" in data
    assert len(data["sites"]) == 1
    assert data["sites"][0]["site_id"] == "chn-01"

    # GET /sites/chn-01
    resp = api.handler(make_event("GET", "/sites/chn-01"))
    assert resp["statusCode"] == 200
    site_obj = json.loads(resp["body"])
    assert site_obj["site_id"] == "chn-01"

    # GET /sites/nonexistent
    resp = api.handler(make_event("GET", "/sites/nonexistent"))
    assert resp["statusCode"] == 404
    err = json.loads(resp["body"])
    assert err["error"]["code"] == "not_found"


def test_post_sites_auth_and_validation(mock_dynamodb):
    """POST /sites requires demo key, validates input, ignores unknown fields, and handles limits."""
    valid_payload = sample_site(site_id="new-01", name="New Site", extra_unknown="ignore_me")

    # 1. Missing demo key -> 401
    resp = api.handler(make_event("POST", "/sites", body=json.dumps(valid_payload)))
    assert resp["statusCode"] == 401

    # 2. Valid create with key -> 201
    resp = api.handler(
        make_event(
            "POST",
            "/sites",
            headers={"x-demo-key": "test-secret-key-12345"},
            body=json.dumps(valid_payload),
        )
    )
    assert resp["statusCode"] == 201
    created = json.loads(resp["body"])
    assert created["site_id"] == "new-01"
    assert "extra_unknown" not in created  # Unknown field ignored

    # 3. Duplicate site_id -> 409
    resp = api.handler(
        make_event(
            "POST",
            "/sites",
            headers={"x-demo-key": "test-secret-key-12345"},
            body=json.dumps(valid_payload),
        )
    )
    assert resp["statusCode"] == 409
    assert json.loads(resp["body"])["error"]["code"] == "conflict"

    # 4. Auto-generate site_id when missing -> 201
    no_id_payload = sample_site(site_id="", name="Auto ID Site")
    resp = api.handler(
        make_event(
            "POST",
            "/sites",
            headers={"x-demo-key": "test-secret-key-12345"},
            body=json.dumps(no_id_payload),
        )
    )
    assert resp["statusCode"] == 201
    auto_created = json.loads(resp["body"])
    assert auto_created["site_id"].startswith("site-")
    assert len(auto_created["site_id"]) == 11

    # 5. Invalid validation (e.g. lat out of India bounds) -> 400
    invalid_payload = sample_site(site_id="bad-lat", lat=5.0)
    resp = api.handler(
        make_event(
            "POST",
            "/sites",
            headers={"x-demo-key": "test-secret-key-12345"},
            body=json.dumps(invalid_payload),
        )
    )
    assert resp["statusCode"] == 400
    assert json.loads(resp["body"])["error"]["code"] == "bad_request"


def test_post_sites_limit_reached(mock_dynamodb):
    """POST /sites returns 409 when 25 sites already exist."""
    for i in range(25):
        db.put_site(mock_dynamodb, sample_site(site_id=f"site-{i:02d}"))

    extra_payload = sample_site(site_id="site-extra")
    resp = api.handler(
        make_event(
            "POST",
            "/sites",
            headers={"x-demo-key": "test-secret-key-12345"},
            body=json.dumps(extra_payload),
        )
    )
    assert resp["statusCode"] == 409
    assert "site limit reached" in json.loads(resp["body"])["error"]["message"]


def test_input_hardening(mock_dynamodb):
    """Reject bodies above 8 KB, reject invalid JSON."""
    # Body > 8 KB
    large_body = json.dumps({"site_id": "huge", "padding": "x" * 9000})
    resp = api.handler(
        make_event(
            "POST",
            "/sites",
            headers={"x-demo-key": "test-secret-key-12345"},
            body=large_body,
        )
    )
    assert resp["statusCode"] == 400
    assert "8 KB" in json.loads(resp["body"])["error"]["message"]

    # Invalid JSON
    resp = api.handler(
        make_event(
            "POST",
            "/sites",
            headers={"x-demo-key": "test-secret-key-12345"},
            body="not-json{",
        )
    )
    assert resp["statusCode"] == 400
    assert "Invalid JSON" in json.loads(resp["body"])["error"]["message"]


def test_get_site_plan_flow(mock_dynamodb, monkeypatch):
    """GET /sites/{site_id}/plan date range, caching (HIT/MISS), and error mapping."""
    db.put_site(mock_dynamodb, sample_site(site_id="chn-01"))

    # Monkeypatch weather fetch
    from shramshield_core import weather

    monkeypatch.setattr(weather, "fetch_forecast", fake_open_meteo_forecast)

    today = datetime.now(INDIA_TZ).date()

    # 1. Fresh request (MISS)
    resp = api.handler(make_event("GET", "/sites/chn-01/plan"))
    assert resp["statusCode"] == 200
    assert resp["headers"].get("x-cache") == "MISS"
    plan_data = json.loads(resp["body"])
    assert plan_data["site_id"] == "chn-01"
    assert len(plan_data["hours"]) == 24

    # 2. Cached request (HIT)
    resp = api.handler(make_event("GET", "/sites/chn-01/plan"))
    assert resp["statusCode"] == 200
    assert resp["headers"].get("x-cache") == "HIT"

    # 3. Allowed date range checks
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    two_days_ahead = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    three_days_ahead = (today + timedelta(days=3)).strftime("%Y-%m-%d")
    two_days_ago = (today - timedelta(days=2)).strftime("%Y-%m-%d")

    # Yesterday -> 200
    resp = api.handler(make_event("GET", "/sites/chn-01/plan", query_params={"date": yesterday}))
    assert resp["statusCode"] == 200

    # 2 days ahead -> 200
    resp = api.handler(make_event("GET", "/sites/chn-01/plan", query_params={"date": two_days_ahead}))
    assert resp["statusCode"] == 200

    # 3 days ahead -> 400
    resp = api.handler(make_event("GET", "/sites/chn-01/plan", query_params={"date": three_days_ahead}))
    assert resp["statusCode"] == 400
    assert "date must be between" in json.loads(resp["body"])["error"]["message"]

    # 2 days ago -> 400
    resp = api.handler(make_event("GET", "/sites/chn-01/plan", query_params={"date": two_days_ago}))
    assert resp["statusCode"] == 400

    # 4. Upstream WeatherError mapping -> 502
    def failing_fetch(lat, lon):
        raise WeatherError("Open-Meteo connection timed out")

    from shramshield_core import plan
    monkeypatch.setattr(weather, "fetch_forecast", failing_fetch)
    monkeypatch.setitem(plan.build_plan_for_site.__kwdefaults__, "fetch", failing_fetch)
    resp = api.handler(
        make_event("GET", "/sites/chn-01/plan", query_params={"date": tomorrow})
    )
    assert resp["statusCode"] == 502
    err_body = json.loads(resp["body"])
    assert err_body["error"]["code"] == "upstream_error"
    assert err_body["error"]["message"] == "weather service unavailable"


# ---------------------------------------------------------------------------
# P2.3 Workflow, Escalation, Telegram, Voice, and State Machine Tests
# ---------------------------------------------------------------------------


def test_asl_json_valid_graph():
    """Verify that escalation.asl.json parses and every Next/Catch target exists."""
    asl_file = backend_dir / "statemachine" / "escalation.asl.json"
    assert asl_file.exists(), f"Missing ASL file at {asl_file}"

    with open(asl_file, "r", encoding="utf-8") as f:
        asl_data = json.load(f)

    states = asl_data.get("States", {})
    required_states = [
        "NotifyPrimary",
        "RecordEscalated",
        "NotifyBackup",
        "RecordUnacknowledged",
        "RecordFailed",
        "Done",
    ]
    for req_st in required_states:
        assert req_st in states, f"Required state '{req_st}' missing from ASL"

    assert states["Done"].get("Type") == "Succeed"

    # Verify all Next and Catch targets exist
    for state_name, state_def in states.items():
        if "Next" in state_def:
            next_target = state_def["Next"]
            assert next_target in states, f"State '{state_name}' Next target '{next_target}' does not exist"

        for catch in state_def.get("Catch", []):
            catch_target = catch.get("Next")
            assert catch_target in states, f"State '{state_name}' Catch target '{catch_target}' does not exist"


def test_no_secrets_in_tracked_files():
    """Verify that no file in backend/ contains bot token strings matching the regex."""
    import re
    token_re = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{35}")

    for root, dirs, files in os.walk(backend_dir):
        # Ignore virtual envs, caches, build
        if any(ign in root for ign in [".venv", "venv", "__pycache__", ".pytest_cache", "build"]):
            continue
        for file in files:
            if file.endswith((".py", ".yaml", ".yml", ".json", ".md")):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    matches = token_re.findall(content)
                    assert not matches, f"Secret token pattern found in {file_path}: {matches}"


def test_notify_primary_happy_path(mock_dynamodb, monkeypatch):
    """Notify primary creates events, stores token, calls telegram and voice."""
    import notify
    from common import runs, telegram, voice

    site = sample_site(
        site_id="chn-01",
        supervisor={"name": "Kavitha", "telegram_chat_id": 12345678},
        language="hi",
        ack_timeout_seconds=600,
    )
    db.put_site(mock_dynamodb, site)

    plan_obj = {
        "plan_id": "chn-01_2026-10-11",
        "site_id": "chn-01",
        "messages": {"hi": "आज गर्मी का खतरा मध्यम रहेगा।", "en": "Moderate heat today."},
        "disclaimer": "Screening advice only.",
        "summary": {"peak_wbgt_c": 31.0, "peak_hour": 14},
    }
    db.put_cached_plan(mock_dynamodb, "chn-01", "2026-10-11", plan_obj, ttl_seconds=1200)

    run_id = "chn-01_20261011T003000"
    runs.create_run(mock_dynamodb, run_id, "chn-01", "chn-01_2026-10-11")

    # Fakes
    telegram_calls = []

    def fake_send_message(chat_id, text, reply_markup=None):
        telegram_calls.append({"type": "msg", "chat_id": chat_id, "text": text, "markup": reply_markup})
        return {"ok": True}

    def fake_send_audio(chat_id, audio_url, caption=None, title=None):
        telegram_calls.append({"type": "audio", "chat_id": chat_id, "audio_url": audio_url})
        return {"ok": True}

    def fake_synthesize(text, r_id, lang="hi"):
        return f"https://mock-s3.amazonaws.com/{r_id}_{lang}.mp3"

    monkeypatch.setattr(telegram, "send_message", fake_send_message)
    monkeypatch.setattr(telegram, "send_audio", fake_send_audio)
    monkeypatch.setattr(voice, "synthesize", fake_synthesize)

    # Invoke notify handler
    event = {
        "action": "notify",
        "stage": "primary",
        "run_id": run_id,
        "site_id": "chn-01",
        "token": "fake-task-token-primary-12345",
    }
    result = notify.handler(event)
    assert result.get("status") == "waiting_ack"

    # Verify task token stored
    stored_token = runs.get_token(mock_dynamodb, run_id, "primary")
    assert stored_token == "fake-task-token-primary-12345"

    # Verify run updated
    run_record = runs.get_run(mock_dynamodb, run_id)
    assert run_record["status"] == "WAITING_ACK"
    assert run_record["active_stage"] == "primary"
    assert run_record["voice_url"] == f"https://mock-s3.amazonaws.com/{run_id}_hi.mp3"

    # Verify events
    steps = [e["step"] for e in run_record["events"]]
    assert "voice_ready" in steps
    assert "telegram_sent" in steps
    assert "notified_primary" in steps

    # Verify telegram message sent with inline acknowledge button
    assert len(telegram_calls) == 2
    msg_call = telegram_calls[0]
    assert msg_call["chat_id"] == 12345678
    assert f"ack:{run_id}" in json.dumps(msg_call["markup"])


def test_ack_closes_run_and_double_ack_returns_409(mock_dynamodb, monkeypatch):
    """POST /ack closes the run; subsequent ack returns 409 conflict."""
    from common import runs

    run_id = "chn-01_20261011T003000"
    runs.create_run(mock_dynamodb, run_id, "chn-01", "chn-01_2026-10-11")
    runs.save_token(mock_dynamodb, run_id, "primary", "primary-token-abc")
    runs.update_run_stage(mock_dynamodb, run_id, "WAITING_ACK", "primary", "2026-10-11T01:00:00Z")

    sfn_success_called = []

    class MockSfnClient:
        def send_task_success(self, taskToken, output):
            sfn_success_called.append(taskToken)
            return {}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda service, **kwargs: MockSfnClient() if service == "stepfunctions" else None)

    # 1. First ack -> 200
    ack_event = make_event(
        "POST",
        "/ack",
        headers={"x-demo-key": "test-secret-key-12345"},
        body=json.dumps({"run_id": run_id, "by": "Kavitha"}),
    )
    resp = api.handler(ack_event)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"ok": True, "status": "ACKNOWLEDGED"}
    assert sfn_success_called == ["primary-token-abc"]

    # Verify run state in DynamoDB
    run = runs.get_run(mock_dynamodb, run_id)
    assert run["status"] == "ACKNOWLEDGED"
    assert run["acked_by"] == "Kavitha"
    assert run["acked_via"] == "web"
    assert run["active_stage"] is None

    # 2. Double ack -> 409 conflict
    resp2 = api.handler(ack_event)
    assert resp2["statusCode"] == 409
    assert json.loads(resp2["body"])["error"]["code"] == "conflict"


def test_ack_after_timeout_race_closes_via_backup(mock_dynamodb, monkeypatch):
    """Ack when status is ESCALATED closes run and sends success with backup token."""
    from common import runs

    run_id = "del-01_20261011T003000"
    runs.create_run(mock_dynamodb, run_id, "del-01", "del-01_2026-10-11")
    runs.save_token(mock_dynamodb, run_id, "backup", "backup-token-xyz")
    runs.update_run_stage(mock_dynamodb, run_id, "ESCALATED", "backup", "2026-10-11T01:00:00Z")

    sfn_success_called = []

    class MockSfnClient:
        def send_task_success(self, taskToken, output):
            sfn_success_called.append(taskToken)
            return {}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda service, **kwargs: MockSfnClient() if service == "stepfunctions" else None)

    ack_event = make_event(
        "POST",
        "/ack",
        headers={"x-demo-key": "test-secret-key-12345"},
        body=json.dumps({"run_id": run_id, "by": "BackupPerson"}),
    )
    resp = api.handler(ack_event)
    assert resp["statusCode"] == 200
    assert sfn_success_called == ["backup-token-xyz"]

    run = runs.get_run(mock_dynamodb, run_id)
    assert run["status"] == "ACKNOWLEDGED"
    assert run["active_stage"] is None


def test_record_escalate_skipped_when_already_acknowledged(mock_dynamodb):
    """record.py returns {"skipped": True} when run is already ACKNOWLEDGED."""
    from common import runs
    import record

    run_id = "chn-01_closed"
    runs.create_run(mock_dynamodb, run_id, "chn-01", "chn-01_2026-10-11")
    runs.close_run_ack(mock_dynamodb, run_id, by="Admin", via="web")

    event = {"action": "escalate", "run_id": run_id}
    res = record.handler(event)
    assert res == {"skipped": True}

    # Verify status did not change
    run = runs.get_run(mock_dynamodb, run_id)
    assert run["status"] == "ACKNOWLEDGED"


def test_telegram_webhook_secret_verification_and_start(mock_dynamodb, monkeypatch):
    """POST /telegram/webhook rejects invalid secrets and handles /start."""
    from common import telegram

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret-telegram-token")

    telegram_sent = []

    def fake_send_message(chat_id, text, reply_markup=None):
        telegram_sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(telegram, "send_message", fake_send_message)

    # 1. Missing secret header -> 401
    resp = api.handler(make_event("POST", "/telegram/webhook", body="{}"))
    assert resp["statusCode"] == 401

    # 2. Wrong secret header -> 401
    resp = api.handler(
        make_event(
            "POST",
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            body="{}",
        )
    )
    assert resp["statusCode"] == 401

    # 3. Valid secret with /start -> 200, replies with chat id
    start_payload = {
        "message": {
            "message_id": 1,
            "text": "/start",
            "chat": {"id": 888777, "type": "private"},
            "from": {"id": 888777, "first_name": "TestUser"},
        }
    }
    resp = api.handler(
        make_event(
            "POST",
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret-telegram-token"},
            body=json.dumps(start_payload),
        )
    )
    assert resp["statusCode"] == 200
    assert len(telegram_sent) == 1
    assert telegram_sent[0][0] == 888777
    assert "888777" in telegram_sent[0][1]


def test_telegram_webhook_callback_ack(mock_dynamodb, monkeypatch):
    """POST /telegram/webhook acknowledges run via inline button callback."""
    from common import runs, telegram

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret-telegram-token")

    run_id = "chn-01_tg_ack"
    runs.create_run(mock_dynamodb, run_id, "chn-01", "chn-01_2026-10-11")
    runs.save_token(mock_dynamodb, run_id, "primary", "token-for-sfn")
    runs.update_run_stage(mock_dynamodb, run_id, "WAITING_ACK", "primary", "2026-10-11T01:00:00Z")

    answered_callbacks = []

    def fake_answer_callback(cb_id, text=None):
        answered_callbacks.append((cb_id, text))
        return {"ok": True}

    monkeypatch.setattr(telegram, "answer_callback", fake_answer_callback)

    cb_payload = {
        "callback_query": {
            "id": "cb_query_123",
            "from": {"first_name": "Kavitha", "id": 12345},
            "data": f"ack:{run_id}",
        }
    }

    # 1. First click: Acknowledged ✅
    resp = api.handler(
        make_event(
            "POST",
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret-telegram-token"},
            body=json.dumps(cb_payload),
        )
    )
    assert resp["statusCode"] == 200
    assert ("cb_query_123", "Acknowledged ✅") in answered_callbacks

    run = runs.get_run(mock_dynamodb, run_id)
    assert run["status"] == "ACKNOWLEDGED"
    assert run["acked_by"] == "Kavitha"
    assert run["acked_via"] == "telegram"

    # 2. Second click: Already closed
    resp2 = api.handler(
        make_event(
            "POST",
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret-telegram-token"},
            body=json.dumps(cb_payload),
        )
    )
    assert resp2["statusCode"] == 200
    assert ("cb_query_123", "Already closed") in answered_callbacks


def test_run_start_conflict_when_active(mock_dynamodb, monkeypatch):
    """POST /sites/{site_id}/run returns 409 conflict when a run is active (< 1 hour)."""
    from common import runs

    site = sample_site(site_id="chn-01")
    db.put_site(mock_dynamodb, site)

    active_run_id = "chn-01_active"
    runs.create_run(mock_dynamodb, active_run_id, "chn-01", "chn-01_2026-10-11")
    runs.update_run_stage(mock_dynamodb, active_run_id, "WAITING_ACK", "primary", "2026-10-11T01:00:00Z")

    resp = api.handler(
        make_event(
            "POST",
            "/sites/chn-01/run",
            headers={"x-demo-key": "test-secret-key-12345"},
            body=json.dumps({"ack_timeout_seconds": 60}),
        )
    )
    assert resp["statusCode"] == 409
    err = json.loads(resp["body"])
    assert err["error"]["code"] == "conflict"
    assert "a run is already active" in err["error"]["message"]


def test_get_run_and_latest_run(mock_dynamodb):
    """GET /sites/{site_id}/runs/latest and GET /runs/{run_id} return run or 404."""
    from common import runs

    site = sample_site(site_id="kol-01")
    db.put_site(mock_dynamodb, site)

    # 404 when no runs exist
    resp = api.handler(make_event("GET", "/sites/kol-01/runs/latest"))
    assert resp["statusCode"] == 404

    run_id = "kol-01_20261011T004000"
    runs.create_run(mock_dynamodb, run_id, "kol-01", "kol-01_2026-10-11", initial_event_detail="peak WBGT 31.0")

    # Latest run
    resp = api.handler(make_event("GET", "/sites/kol-01/runs/latest"))
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])
    assert data["run_id"] == run_id

    # Get by run_id
    resp = api.handler(make_event("GET", f"/runs/{run_id}"))
    assert resp["statusCode"] == 200
    data = json.loads(resp["body"])
    assert data["run_id"] == run_id
    assert data["status"] == "STARTED"

    # Nonexistent run -> 404
    resp = api.handler(make_event("GET", "/runs/nonexistent-run"))
    assert resp["statusCode"] == 404


def test_seed_sites_set_chat(mock_dynamodb, monkeypatch):
    """Test set-chat updates chat id as integer, preserves other fields, and handles errors."""
    import importlib.util
    import boto3

    seed_script_path = backend_dir / "scripts" / "seed_sites.py"
    spec = importlib.util.spec_from_file_location("seed_sites", seed_script_path)
    seed_sites = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_sites)

    # Setup initial site
    site = sample_site(
        site_id="chn-01",
        name="Chennai Demo",
        lat=13.08,
        lon=80.21,
        supervisor={"name": "Alice", "telegram_chat_id": None},
        backup={"name": "Bob", "telegram_chat_id": None},
    )
    db.put_site(mock_dynamodb, site)

    # 1. Update supervisor chat ID
    res = seed_sites.set_chat(mock_dynamodb, "chn-01", "supervisor", "987654321")
    assert res == 0

    updated = db.get_site(mock_dynamodb, "chn-01")
    assert updated["supervisor"]["telegram_chat_id"] == 987654321
    assert isinstance(updated["supervisor"]["telegram_chat_id"], int)
    # Ensure other fields are never overwritten
    assert updated["supervisor"]["name"] == "Alice"
    assert updated["name"] == "Chennai Demo"
    assert updated["lat"] == 13.08
    assert updated["backup"]["telegram_chat_id"] is None

    # 2. Update backup chat ID
    res = seed_sites.set_chat(mock_dynamodb, "chn-01", "backup", 123456789)
    assert res == 0
    updated = db.get_site(mock_dynamodb, "chn-01")
    assert updated["backup"]["telegram_chat_id"] == 123456789
    assert isinstance(updated["backup"]["telegram_chat_id"], int)
    assert updated["backup"]["name"] == "Bob"
    assert updated["supervisor"]["telegram_chat_id"] == 987654321

    # 3. Fail clearly if site does not exist
    res = seed_sites.set_chat(mock_dynamodb, "nonexistent-site", "supervisor", "123")
    assert res == 1

    # 4. Fail clearly if chat_id is not integer
    res = seed_sites.set_chat(mock_dynamodb, "chn-01", "supervisor", "not-a-number")
    assert res == 1

    # 5. Fail clearly if role is invalid
    res = seed_sites.set_chat(mock_dynamodb, "chn-01", "invalid_role", "123")
    assert res == 1

    # 6. Test CLI argument parsing via main() with mock table
    monkeypatch.setattr(boto3, "resource", lambda s, **kwargs: type("M", (), {"Table": lambda self, name: mock_dynamodb})())
    monkeypatch.setattr(seed_sites, "resolve_table_name", lambda s, r: "test-table")

    # Flag before command: seed_sites.py --stack shramshield set-chat chn-01 supervisor 55555
    res = seed_sites.main(["--stack", "shramshield", "set-chat", "chn-01", "supervisor", "55555"])
    assert res == 0
    updated = db.get_site(mock_dynamodb, "chn-01")
    assert updated["supervisor"]["telegram_chat_id"] == 55555
    assert isinstance(updated["supervisor"]["telegram_chat_id"], int)

    # Flag after command: seed_sites.py set-chat chn-01 backup 66666 --stack shramshield
    res = seed_sites.main(["set-chat", "chn-01", "backup", "66666", "--stack", "shramshield"])
    assert res == 0
    updated = db.get_site(mock_dynamodb, "chn-01")
    assert updated["backup"]["telegram_chat_id"] == 66666
    assert isinstance(updated["backup"]["telegram_chat_id"], int)


def test_notify_ack_deadline_uses_run_timeout_override_60s(mock_dynamodb, monkeypatch):
    """Verify that run.ack_deadline uses the run's 60s override instead of site's default (900s)."""
    import notify
    from common import runs, telegram, voice

    # Site with default timeout = 900 seconds
    site = sample_site(
        site_id="chn-01",
        supervisor={"name": "Kavitha", "telegram_chat_id": 11111},
        backup={"name": "Rajesh", "telegram_chat_id": 22222},
        ack_timeout_seconds=900,
    )
    db.put_site(mock_dynamodb, site)

    plan_obj = {
        "plan_id": "chn-01_2026-10-11",
        "site_id": "chn-01",
        "messages": {"hi": "आज गर्मी का खतरा मध्यम रहेगा।", "en": "Moderate heat today."},
        "disclaimer": "Screening advice only.",
        "summary": {"peak_wbgt_c": 31.0, "peak_hour": 14},
    }
    db.put_cached_plan(mock_dynamodb, "chn-01", "2026-10-11", plan_obj, ttl_seconds=1200)

    # 1. Primary stage with 60s override
    run_id = "chn-01_override_run"
    runs.create_run(mock_dynamodb, run_id, "chn-01", "chn-01_2026-10-11", ack_timeout_seconds=60)

    monkeypatch.setattr(telegram, "send_message", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(telegram, "send_audio", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(voice, "synthesize", lambda *args, **kwargs: "https://mock/v.mp3")

    event_primary = {
        "action": "notify",
        "stage": "primary",
        "run_id": run_id,
        "site_id": "chn-01",
        "token": "tok-prim-60s",
        "ack_timeout_seconds": 60,
    }
    res_primary = notify.handler(event_primary)
    assert res_primary.get("status") == "waiting_ack"

    run_rec = runs.get_run(mock_dynamodb, run_id)
    assert run_rec["status"] == "WAITING_ACK"
    assert run_rec["active_stage"] == "primary"

    deadline_dt = datetime.strptime(run_rec["ack_deadline"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    now_dt = datetime.now(timezone.utc)
    delta_secs = (deadline_dt - now_dt).total_seconds()
    # Should be approximately 60 seconds (55..65s), definitely not 900s!
    assert 55 <= delta_secs <= 65, f"Expected ~60s deadline, got {delta_secs}s (site default is 900s)"

    # 2. Backup stage with 60s override
    event_backup = {
        "action": "notify",
        "stage": "backup",
        "run_id": run_id,
        "site_id": "chn-01",
        "token": "tok-back-60s",
        "ack_timeout_seconds": 60,
    }
    res_backup = notify.handler(event_backup)
    assert res_backup.get("status") == "waiting_ack"

    run_rec_backup = runs.get_run(mock_dynamodb, run_id)
    assert run_rec_backup["active_stage"] == "backup"
    deadline_backup_dt = datetime.strptime(run_rec_backup["ack_deadline"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    now_backup_dt = datetime.now(timezone.utc)
    delta_backup_secs = (deadline_backup_dt - now_backup_dt).total_seconds()
    assert 55 <= delta_backup_secs <= 65, f"Expected ~60s backup deadline, got {delta_backup_secs}s"


