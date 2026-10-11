"""Shared logic for starting a heat safety workflow run.

Called by API POST /sites/{id}/run and by the morning EventBridge scheduler.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

import boto3

try:
    from common import db, runs
    from common.http import error
except ImportError:
    from src.common import db, runs
    from src.common.http import error

logger = logging.getLogger("runs_start")
logger.setLevel(logging.INFO)

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))


def start_run_for_site(
    table: Any,
    site: Dict[str, Any],
    ack_timeout_seconds: Optional[int] = None,
    state_machine_arn: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Start an alert workflow execution for a given site.

    Returns (status_code, response_dict).
    """
    site_id = site["site_id"]

    # Validate timeout
    if ack_timeout_seconds is not None:
        if not isinstance(ack_timeout_seconds, int) or not (30 <= ack_timeout_seconds <= 3600):
            return 400, error("bad_request", "ack_timeout_seconds must be between 30 and 3600")
        timeout = ack_timeout_seconds
    else:
        timeout = site.get("ack_timeout_seconds", 900)

    # Check for active run conflict (less than 1 hour old and non-final)
    latest_run = runs.get_latest_run(table, site_id)
    if latest_run and latest_run.get("status") in ("STARTED", "WAITING_ACK", "ESCALATED"):
        try:
            created_dt = datetime.strptime(latest_run["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            if (now_utc - created_dt).total_seconds() < 3600:
                return 409, error("conflict", "a run is already active")
        except Exception as exc:
            logger.warning("Error parsing created_at on latest run: %s", exc)

    # Build plan (cache first)
    today_india = datetime.now(INDIA_TZ).date().strftime("%Y-%m-%d")
    plan = db.get_cached_plan(table, site_id, today_india)
    if not plan:
        try:
            from shramshield_core.plan import build_plan_for_site
            from shramshield_core.weather import WeatherError
        except ImportError:
            from src.shramshield_core.plan import build_plan_for_site
            from src.shramshield_core.weather import WeatherError

        try:
            plan = build_plan_for_site(site, date_str=today_india)
            ttl = int(os.environ.get("WEATHER_CACHE_SECONDS", "1200"))
            db.put_cached_plan(table, site_id, today_india, plan, ttl)
        except WeatherError:
            return 502, error("upstream_error", "weather service unavailable")

    summary = plan.get("summary", {})
    peak_wbgt = summary.get("peak_wbgt_c")
    peak_hour = summary.get("peak_hour")
    if peak_wbgt is not None and peak_hour is not None:
        detail_msg = f"peak WBGT {float(peak_wbgt):.1f} at {peak_hour:02d}:00"
    else:
        detail_msg = "plan built"

    # Contract 3.2: run_id is site_id + "_" + UTC time "YYYYMMDDTHHMMSS"
    utc_now = datetime.now(timezone.utc)
    run_id = f"{site_id}_{utc_now.strftime('%Y%m%dT%H%M%S')}"
    plan_id = plan["plan_id"]

    run_obj = runs.create_run(
        table,
        run_id,
        site_id,
        plan_id,
        initial_event_detail=detail_msg,
        ack_timeout_seconds=timeout,
    )

    sm_arn = state_machine_arn or os.environ.get("STATE_MACHINE_ARN")
    if not sm_arn:
        logger.error("STATE_MACHINE_ARN not configured, cannot start workflow.")
        runs.set_run_status(table, run_id, "FAILED", event_step="error", event_detail="State machine ARN not configured")
        return 500, error("internal", "State machine not configured")

    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
    sfn = boto3.client("stepfunctions", region_name=region)

    try:
        sfn_input = {
            "run_id": run_id,
            "site_id": site_id,
            "ack_timeout_seconds": timeout,
        }
        logger.info("Starting Step Functions execution for run %s (timeout: %ds)", run_id, timeout)
        sfn.start_execution(
            stateMachineArn=sm_arn,
            name=run_id,
            input=json.dumps(sfn_input),
        )
    except Exception as exc:
        logger.error("Failed to start Step Functions execution for %s: %s", run_id, exc)
        runs.set_run_status(table, run_id, "FAILED", event_step="error", event_detail=f"Execution error: {type(exc).__name__}")
        return 500, error("internal", "Failed to start state machine execution")

    return 202, {"run_id": run_id, "status": "STARTED"}
