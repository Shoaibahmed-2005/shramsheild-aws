"""HTTP helpers and utilities for API Gateway Payload 2.0 handlers."""

import hmac
import json
import os
from typing import Any, Dict, Optional

# Contract 3.9 status mapping
ERROR_STATUS_CODES = {
    "bad_request": 400,
    "unauthorized": 401,
    "not_found": 404,
    "conflict": 409,
    "upstream_error": 502,
    "internal": 500,
}


def json_response(
    status: int,
    body_dict: Dict[str, Any],
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build an API Gateway payload 2.0 JSON response."""
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body_dict),
    }


def error(code: str, message: str) -> Dict[str, Any]:
    """Build a standard contract error response."""
    status = ERROR_STATUS_CODES.get(code, 500)
    return json_response(status, {"error": {"code": code, "message": message}})


def require_demo_key(event: Dict[str, Any]) -> bool:
    """Validate x-demo-key header against DEMO_KEY environment variable.

    Uses constant-time comparison via hmac.compare_digest.
    Fails closed if DEMO_KEY is empty or 'not-set'.
    """
    configured_key = os.environ.get("DEMO_KEY", "").strip()
    if not configured_key or configured_key == "not-set":
        return False

    raw_headers = event.get("headers") or {}
    headers = {str(k).lower(): str(v) for k, v in raw_headers.items()}
    header_key = headers.get("x-demo-key", "").strip()

    if not header_key:
        return False

    return hmac.compare_digest(header_key, configured_key)
