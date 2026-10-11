"""Step Functions Record Lambda task for managing escalation transitions and failures."""

import logging
import os
from typing import Any, Dict

import boto3

try:
    from common import runs
except ImportError:
    from src.common import runs

logger = logging.getLogger("record")
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
    """Execute state machine record updates."""
    action = event.get("action")
    run_id = event.get("run_id")
    error_info = event.get("error")

    if not run_id:
        logger.error("Missing run_id in record event: %s", event)
        return {"error": "Missing run_id"}

    table = _get_table()
    run = runs.get_run(table, run_id)
    if not run:
        logger.warning("Run %s not found for record action %s", run_id, action)
        return {"skipped": True}

    if run.get("status") in runs.FINAL_STATUSES:
        logger.info("Run %s already final (%s). Skipping action %s.", run_id, run.get("status"), action)
        return {"skipped": True}

    if action == "escalate":
        # Transition WAITING_ACK -> ESCALATED, active_stage = backup
        success = runs.set_run_status(
            table,
            run_id,
            new_status="ESCALATED",
            active_stage="backup",
            event_step="escalated",
            event_detail="primary did not acknowledge in time",
            allowed_from_statuses=["WAITING_ACK"],
        )
        if not success:
            logger.info("Escalate skipped for run %s (run already final or closed)", run_id)
            return {"skipped": True}
        logger.info("Escalated run %s", run_id)
        return {"status": "escalated", "success": True}

    elif action == "unacknowledge":
        # Transition to UNACKNOWLEDGED, active_stage = None
        success = runs.set_run_status(
            table,
            run_id,
            new_status="UNACKNOWLEDGED",
            active_stage=None,
            event_step="unacknowledged",
            event_detail="nobody acknowledged before deadline",
            allowed_from_statuses=["ESCALATED", "WAITING_ACK"],
        )
        if not success:
            logger.info("Unacknowledge skipped for run %s (run already closed)", run_id)
            return {"skipped": True}
        logger.info("Unacknowledged run %s", run_id)
        return {"status": "unacknowledged", "success": True}

    elif action == "fail":
        # Transition to FAILED, active_stage = None
        err_msg = "error"
        if error_info:
            if isinstance(error_info, dict):
                err_msg = error_info.get("Error") or error_info.get("Cause") or "error"
            else:
                err_msg = str(error_info)

        success = runs.set_run_status(
            table,
            run_id,
            new_status="FAILED",
            active_stage=None,
            event_step="error",
            event_detail=str(err_msg)[:100],
        )
        if not success:
            logger.info("Fail skipped for run %s (run already closed)", run_id)
            return {"skipped": True}
        logger.info("Marked run %s as FAILED", run_id)
        return {"status": "failed", "success": True}

    else:
        logger.warning("Unknown record action: %s", action)
        return {"error": f"Unknown action: {action}"}
