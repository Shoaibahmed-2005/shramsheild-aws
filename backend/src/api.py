"""ShramShield HTTP API router and Lambda handler.

Implements API Gateway Payload 2.0 handling with safe logging,
HMAC-based demo key protection, DynamoDB site storage, and weather plan generation.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import os
import random
import re
import string
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from common.http import error, json_response, require_demo_key
    from common import db
except ImportError:
    from src.common.http import error, json_response, require_demo_key
    from src.common import db

logger = logging.getLogger("api")
logger.setLevel(logging.INFO)

_SITE_ID_RE = re.compile(r"^[a-z0-9-]{3,20}$")
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))
ALLOWED_SITE_FIELDS = {
    "site_id",
    "name",
    "lat",
    "lon",
    "workload",
    "acclimatized",
    "work_start_hour",
    "work_end_hour",
    "language",
    "supervisor",
    "backup",
    "ack_timeout_seconds",
}

_dynamodb_table: Any = None


def get_table() -> Any:
    """Lazy initialize and return the DynamoDB Table resource."""
    global _dynamodb_table
    if _dynamodb_table is not None:
        return _dynamodb_table

    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        raise RuntimeError("TABLE_NAME environment variable not set")

    import boto3

    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
    dynamodb = boto3.resource("dynamodb", region_name=region)
    _dynamodb_table = dynamodb.Table(table_name)
    return _dynamodb_table


def set_table(table: Any) -> None:
    """Set the table resource directly (useful for tests and mocking)."""
    global _dynamodb_table
    _dynamodb_table = table


def _get_thermofeel_version() -> Optional[str]:
    """Guarded import of thermofeel so missing layer returns null instead of crashing."""
    try:
        import thermofeel

        if hasattr(thermofeel, "__version__") and thermofeel.__version__:
            return str(thermofeel.__version__)
        import importlib.metadata

        return importlib.metadata.version("thermofeel")
    except Exception:
        return None


RouteHandler = Callable[..., Dict[str, Any]]


class Router:
    """A lightweight (method, regex_path) router for API Gateway Payload 2.0."""

    def __init__(self) -> None:
        self.routes: List[Tuple[str, re.Pattern, RouteHandler, bool]] = []

    def add(
        self,
        method: str,
        pattern: str,
        handler_fn: RouteHandler,
        require_key: Optional[bool] = None,
    ) -> None:
        meth = method.upper()
        if require_key is None:
            require_key = meth == "POST" and not pattern.startswith(r"^/telegram/webhook")
        self.routes.append((meth, re.compile(pattern), handler_fn, require_key))

    def dispatch(self, event: Dict[str, Any]) -> Dict[str, Any]:
        # Input hardening: reject bodies > 8 KB
        raw_body = event.get("body")
        if raw_body and len(raw_body.encode("utf-8")) > 8192:
            return error("bad_request", "Request body exceeds 8 KB limit")

        http_ctx = event.get("requestContext", {}).get("http", {})
        method = http_ctx.get("method", "GET").upper()
        raw_path = event.get("rawPath", "/")

        for route_method, pattern, handler_fn, require_key in self.routes:
            if route_method == method:
                match = pattern.match(raw_path)
                if match:
                    if require_key:
                        if not require_demo_key(event):
                            return error("unauthorized", "Unauthorized: missing or invalid x-demo-key")
                    return handler_fn(event, *match.groups())

        return error("not_found", f"Route not found: {method} {raw_path}")


router = Router()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_health(event: Dict[str, Any]) -> Dict[str, Any]:
    return json_response(
        200,
        {
            "ok": True,
            "service": "shramshield",
            "version": "0.1.0",
            "thermofeel": _get_thermofeel_version(),
        },
    )


def handle_list_sites(event: Dict[str, Any]) -> Dict[str, Any]:
    table = get_table()
    sites = db.list_sites(table)
    return json_response(200, {"sites": sites})


def handle_get_site(event: Dict[str, Any], site_id: str) -> Dict[str, Any]:
    if not _SITE_ID_RE.match(site_id):
        return error("bad_request", f"site_id '{site_id}' must match ^[a-z0-9-]{{3,20}}$")

    table = get_table()
    site = db.get_site(table, site_id)
    if not site:
        return error("not_found", f"Site '{site_id}' not found")
    return json_response(200, site)


def handle_create_site(event: Dict[str, Any]) -> Dict[str, Any]:
    raw_body = event.get("body")
    if not raw_body:
        return error("bad_request", "Missing request body")

    try:
        body_json = json.loads(raw_body)
    except Exception:
        return error("bad_request", "Invalid JSON body")

    if not isinstance(body_json, dict):
        return error("bad_request", "Request body must be a JSON object")

    # Hardening: ignore unknown fields
    site_dict = {k: v for k, v in body_json.items() if k in ALLOWED_SITE_FIELDS}

    # Generate site_id if absent
    if not site_dict.get("site_id"):
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        site_dict["site_id"] = f"site-{suffix}"

    # Validate against contract single source of truth
    try:
        from shramshield_core.contract import validate_site
    except ImportError:
        from src.shramshield_core.contract import validate_site

    validation_errors = validate_site(site_dict)
    if validation_errors:
        return error("bad_request", "; ".join(validation_errors))

    table = get_table()
    existing_sites = db.list_sites(table)

    # Refuse when table already has 25 sites
    if len(existing_sites) >= 25:
        return error("conflict", "site limit reached")

    # Refuse duplicate site_id
    if any(s.get("site_id") == site_dict["site_id"] for s in existing_sites):
        return error("conflict", f"site_id '{site_dict['site_id']}' already exists")

    db.put_site(table, site_dict)
    return json_response(201, site_dict)


def handle_get_site_plan(event: Dict[str, Any], site_id: str) -> Dict[str, Any]:
    if not _SITE_ID_RE.match(site_id):
        return error("bad_request", f"site_id '{site_id}' must match ^[a-z0-9-]{{3,20}}$")

    table = get_table()
    site = db.get_site(table, site_id)
    if not site:
        return error("not_found", f"Site '{site_id}' not found")

    # India time calculations
    today_india = datetime.now(INDIA_TZ).date()

    query_params = event.get("queryStringParameters") or {}
    date_str = query_params.get("date")

    if not date_str:
        target_date = today_india
        date_str = target_date.strftime("%Y-%m-%d")
    else:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return error("bad_request", "date query parameter must be in YYYY-MM-DD format")

    min_date = today_india - timedelta(days=1)
    max_date = today_india + timedelta(days=2)
    if not (min_date <= target_date <= max_date):
        return error(
            "bad_request",
            f"date must be between {min_date.strftime('%Y-%m-%d')} (yesterday) and {max_date.strftime('%Y-%m-%d')} (2 days ahead)",
        )

    # Cache check
    cached = db.get_cached_plan(table, site_id, date_str)
    if cached:
        return json_response(200, cached, extra_headers={"x-cache": "HIT"})

    # Lazy imports per pitfall note to avoid cold start penalty on other routes
    try:
        from shramshield_core.plan import build_plan_for_site
        from shramshield_core.weather import WeatherError
    except ImportError:
        from src.shramshield_core.plan import build_plan_for_site
        from src.shramshield_core.weather import WeatherError

    try:
        plan = build_plan_for_site(site, date_str=date_str)
    except WeatherError:
        return error("upstream_error", "weather service unavailable")

    weather_cache_seconds = int(os.environ.get("WEATHER_CACHE_SECONDS", "1200"))
    db.put_cached_plan(table, site_id, date_str, plan, weather_cache_seconds)
    return json_response(200, plan, extra_headers={"x-cache": "MISS"})


def handle_unimplemented(event: Dict[str, Any], *args: Any) -> Dict[str, Any]:
    return error("not_found", "not implemented yet")


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

router.add("GET", r"^/health/?$", handle_health, require_key=False)

# Sites routes
router.add("GET", r"^/sites/?$", handle_list_sites, require_key=False)
router.add("POST", r"^/sites/?$", handle_create_site, require_key=True)
router.add("GET", r"^/sites/([a-z0-9-]+)/?$", handle_get_site, require_key=False)
router.add("GET", r"^/sites/([a-z0-9-]+)/plan/?$", handle_get_site_plan, require_key=False)

# Workflow routes (to be implemented in P2.3)
router.add("POST", r"^/sites/([a-zA-Z0-9_-]+)/run/?$", handle_unimplemented, require_key=True)
router.add("GET", r"^/sites/([a-zA-Z0-9_-]+)/runs/latest/?$", handle_unimplemented, require_key=False)
router.add("GET", r"^/runs/([a-zA-Z0-9_-]+)/?$", handle_unimplemented, require_key=False)
router.add("POST", r"^/ack/?$", handle_unimplemented, require_key=True)
router.add("POST", r"^/telegram/webhook/?$", handle_unimplemented, require_key=False)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Top-level AWS Lambda entry point."""
    try:
        return router.dispatch(event)
    except Exception as exc:
        logger.error("Internal error occurred: %s: %s", type(exc).__name__, str(exc))
        return error("internal", "Internal server error")
