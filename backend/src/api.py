"""ShramShield HTTP API router and Lambda handler.

Implements API Gateway Payload 2.0 handling with safe logging,
HMAC-based demo key protection, and contract health checks.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from common.http import error, json_response, require_demo_key
except ImportError:
    from src.common.http import error, json_response, require_demo_key

logger = logging.getLogger("api")
logger.setLevel(logging.INFO)


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


RouteHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


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
        """Register a route with an HTTP method, regex pattern, and handler.

        If require_key is None, POST requests default to requiring demo key
        unless the route is the Telegram webhook.
        """
        meth = method.upper()
        if require_key is None:
            require_key = (meth == "POST" and not pattern.startswith(r"^/telegram/webhook"))

        self.routes.append((meth, re.compile(pattern), handler_fn, require_key))

    def dispatch(self, event: Dict[str, Any]) -> Dict[str, Any]:
        http_ctx = event.get("requestContext", {}).get("http", {})
        method = http_ctx.get("method", "GET").upper()
        raw_path = event.get("rawPath", "/")

        for route_method, pattern, handler_fn, require_key in self.routes:
            if route_method == method and pattern.match(raw_path):
                if require_key:
                    if not require_demo_key(event):
                        return error("unauthorized", "Unauthorized: missing or invalid x-demo-key")
                return handler_fn(event)

        return error("not_found", f"Route not found: {method} {raw_path}")


router = Router()


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


def handle_unimplemented(event: Dict[str, Any]) -> Dict[str, Any]:
    return error("not_found", "not implemented yet")


# Contract routes
router.add("GET", r"^/health/?$", handle_health, require_key=False)

# Contract routes (stubs returning 501-style not_found for P2.1)
router.add("GET", r"^/sites/?$", handle_unimplemented, require_key=False)
router.add("POST", r"^/sites/?$", handle_unimplemented, require_key=True)
router.add("GET", r"^/sites/[a-zA-Z0-9_-]+/?$", handle_unimplemented, require_key=False)
router.add("GET", r"^/sites/[a-zA-Z0-9_-]+/plan/?$", handle_unimplemented, require_key=False)
router.add("POST", r"^/sites/[a-zA-Z0-9_-]+/run/?$", handle_unimplemented, require_key=True)
router.add("GET", r"^/sites/[a-zA-Z0-9_-]+/runs/latest/?$", handle_unimplemented, require_key=False)
router.add("GET", r"^/runs/[a-zA-Z0-9_-]+/?$", handle_unimplemented, require_key=False)
router.add("POST", r"^/ack/?$", handle_unimplemented, require_key=True)
router.add("POST", r"^/telegram/webhook/?$", handle_unimplemented, require_key=False)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Top-level AWS Lambda entry point."""
    try:
        return router.dispatch(event)
    except Exception as exc:
        # Log exception type and message only; never log headers, body, or secrets
        logger.error("Internal error occurred: %s: %s", type(exc).__name__, str(exc))
        return error("internal", "Internal server error")
