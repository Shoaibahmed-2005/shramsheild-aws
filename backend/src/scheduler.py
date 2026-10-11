"""Morning automated scheduler Lambda triggered by EventBridge cron.

Scans sites and initiates heat alert runs for sites with configured supervisors.
"""

import logging
import os
from typing import Any, Dict

import boto3

try:
    from common import db
    from common.runs_start import start_run_for_site
except ImportError:
    from src.common import db
    from src.common.runs_start import start_run_for_site

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)


def _get_table() -> Any:
    try:
        import api
        if getattr(api, "_dynamodb_table", None) is not None:
            return api._dynamodb_table
    except Exception:
        pass
    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        raise RuntimeError("TABLE_NAME environment variable not set")
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(table_name)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Scan all sites and launch workflow runs for those with supervisor chat IDs."""
    logger.info("Scheduler execution triggered. Event: %s", event)

    table = _get_table()
    sites = db.list_sites(table)
    logger.info("Found %d total sites in table", len(sites))

    started = []
    skipped = []

    for site in sites:
        site_id = site.get("site_id")
        supervisor = site.get("supervisor") or {}
        chat_id = supervisor.get("telegram_chat_id")

        if not chat_id:
            logger.info("Skipping site %s: no supervisor chat ID configured", site_id)
            skipped.append({"site_id": site_id, "reason": "no_chat_id"})
            continue

        status_code, result = start_run_for_site(table, site)
        if status_code == 202:
            logger.info("Successfully started run %s for site %s", result.get("run_id"), site_id)
            started.append({"site_id": site_id, "run_id": result.get("run_id")})
        else:
            logger.warning("Could not start run for site %s (status %d): %s", site_id, status_code, result)
            skipped.append({"site_id": site_id, "reason": result})

    summary = {
        "ok": True,
        "started_count": len(started),
        "skipped_count": len(skipped),
        "started": started,
        "skipped": skipped,
    }
    logger.info("Scheduler completed: %s", summary)
    return summary
