"""Tests for ShramShield HTTP API and router."""

import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Ensure backend/src is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
src_dir = backend_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import api
from common.http import json_response


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


def test_health_endpoint():
    """GET /health returns 200 with required contract keys."""
    event = make_event("GET", "/health")
    response = api.handler(event)

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/json"

    data = json.loads(response["body"])
    assert data["ok"] is True
    assert data["service"] == "shramshield"
    assert data["version"] == "0.1.0"
    assert "thermofeel" in data
    # thermofeel will be version string or None


def test_unknown_path_returns_404():
    """Unknown path returns 404 with error body."""
    event = make_event("GET", "/nonexistent/endpoint")
    response = api.handler(event)

    assert response["statusCode"] == 404
    data = json.loads(response["body"])
    assert "error" in data
    assert data["error"]["code"] == "not_found"
    assert "Route not found" in data["error"]["message"]


def test_post_without_demo_key_returns_401(monkeypatch):
    """POST to a protected route without demo key returns 401."""
    monkeypatch.setenv("DEMO_KEY", "test-demo-secret-key-1234")

    # Register a dummy POST route for this test
    def dummy_post(evt):
        return json_response(200, {"success": True})

    api.router.add("POST", r"^/test-dummy-post$", dummy_post, require_key=True)

    event = make_event("POST", "/test-dummy-post", body="{}")
    response = api.handler(event)

    assert response["statusCode"] == 401
    data = json.loads(response["body"])
    assert data["error"]["code"] == "unauthorized"


def test_post_with_wrong_demo_key_returns_401(monkeypatch):
    """POST to a protected route with invalid demo key returns 401."""
    monkeypatch.setenv("DEMO_KEY", "test-demo-secret-key-1234")

    event = make_event(
        "POST",
        "/test-dummy-post",
        headers={"x-demo-key": "wrong-secret-key"},
        body="{}",
    )
    response = api.handler(event)

    assert response["statusCode"] == 401
    data = json.loads(response["body"])
    assert data["error"]["code"] == "unauthorized"


def test_post_with_right_demo_key_reaches_handler(monkeypatch):
    """POST to a protected route with correct demo key reaches handler."""
    secret = "test-demo-secret-key-1234"
    monkeypatch.setenv("DEMO_KEY", secret)

    event = make_event(
        "POST",
        "/test-dummy-post",
        headers={"x-demo-key": secret},
        body="{}",
    )
    response = api.handler(event)

    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    assert data["success"] is True


def test_contract_unimplemented_routes(monkeypatch):
    """Contract routes return 404 not implemented yet in P2.1 skeleton."""
    monkeypatch.setenv("DEMO_KEY", "test-demo-secret-key-1234")

    # GET /sites
    resp = api.handler(make_event("GET", "/sites"))
    assert resp["statusCode"] == 404
    assert json.loads(resp["body"])["error"]["message"] == "not implemented yet"

    # POST /sites with valid key
    resp = api.handler(
        make_event("POST", "/sites", headers={"x-demo-key": "test-demo-secret-key-1234"})
    )
    assert resp["statusCode"] == 404
    assert json.loads(resp["body"])["error"]["message"] == "not implemented yet"


def test_internal_error_returns_500():
    """Exceptions inside handlers are caught and return a clean 500 error."""
    def broken_handler(evt):
        raise RuntimeError("Something crashed internally")

    api.router.add("GET", r"^/crash-test$", broken_handler, require_key=False)

    event = make_event("GET", "/crash-test")
    response = api.handler(event)

    assert response["statusCode"] == 500
    data = json.loads(response["body"])
    assert data["error"]["code"] == "internal"
    assert data["error"]["message"] == "Internal server error"
