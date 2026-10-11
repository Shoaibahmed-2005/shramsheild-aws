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
    assert body["version"] == "0.1.0"
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
