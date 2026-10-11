"""Run management and DynamoDB operations for ShramShield alert workflows.

Implements run state machine storage, conditional updates, task tokens,
and event logging matching Contract 3.5 and 3.10.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from botocore.exceptions import ClientError

try:
    from common.db import from_ddb, to_ddb
except ImportError:
    from src.common.db import from_ddb, to_ddb

logger = logging.getLogger("runs")
logger.setLevel(logging.INFO)

FINAL_STATUSES = {"ACKNOWLEDGED", "UNACKNOWLEDGED", "FAILED"}


def now_utc_iso() -> str:
    """Current UTC timestamp formatted as YYYY-MM-DDTHH:MM:SSZ."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_run(
    table: Any,
    run_id: str,
    site_id: str,
    plan_id: str,
    initial_event_detail: Optional[str] = None,
    ack_timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a new run record and update the site's latest run pointer."""
    now_ts = now_utc_iso()

    events = []
    if initial_event_detail is not None:
        events.append({"ts": now_ts, "step": "plan_built", "detail": initial_event_detail})

    run_obj: Dict[str, Any] = {
        "run_id": run_id,
        "site_id": site_id,
        "plan_id": plan_id,
        "status": "STARTED",
        "active_stage": None,
        "ack_deadline": None,
        "voice_url": None,
        "acked_by": None,
        "acked_via": None,
        "created_at": now_ts,
        "events": events,
    }
    if ack_timeout_seconds is not None:
        run_obj["ack_timeout_seconds"] = int(ack_timeout_seconds)

    # Put run item
    table.put_item(
        Item={
            "PK": f"RUN#{run_id}",
            "SK": "META",
            "data": to_ddb(run_obj),
            "status": "STARTED",
            "site_id": site_id,
        }
    )

    # Put latest pointer item
    table.put_item(
        Item={
            "PK": f"SITE#{site_id}",
            "SK": "LATEST",
            "run_id": run_id,
        }
    )

    return run_obj


def get_run(table: Any, run_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve run by run_id."""
    resp = table.get_item(Key={"PK": f"RUN#{run_id}", "SK": "META"})
    item = resp.get("Item")
    if not item or "data" not in item:
        return None
    return from_ddb(item["data"])


def get_latest_run(table: Any, site_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the latest run for a given site."""
    resp = table.get_item(Key={"PK": f"SITE#{site_id}", "SK": "LATEST"})
    item = resp.get("Item")
    if not item or "run_id" not in item:
        return None
    latest_run_id = item["run_id"]
    return get_run(table, latest_run_id)


def add_event(table: Any, run_id: str, step: str, detail: str) -> None:
    """Append an event to the run's event list."""
    now_ts = now_utc_iso()
    new_event = {"ts": now_ts, "step": step, "detail": detail}

    run = get_run(table, run_id)
    if not run:
        logger.warning("Attempted to add event to nonexistent run: %s", run_id)
        return

    events = run.get("events", [])
    events.append(new_event)
    run["events"] = events

    table.update_item(
        Key={"PK": f"RUN#{run_id}", "SK": "META"},
        UpdateExpression="SET #d.#ev = :ev",
        ExpressionAttributeNames={"#d": "data", "#ev": "events"},
        ExpressionAttributeValues={":ev": to_ddb(events)},
    )


def save_token(
    table: Any,
    run_id: str,
    stage: str,
    token: str,
    ttl_seconds: int = 7200,
) -> None:
    """Store Step Functions Task Token in DynamoDB with TTL."""
    ttl_epoch = int(time.time()) + ttl_seconds
    table.put_item(
        Item={
            "PK": f"RUN#{run_id}",
            "SK": f"TOKEN#{stage}",
            "token": token,
            "ttl": ttl_epoch,
        }
    )


def get_token(table: Any, run_id: str, stage: str) -> Optional[str]:
    """Retrieve stored Task Token for a stage."""
    resp = table.get_item(Key={"PK": f"RUN#{run_id}", "SK": f"TOKEN#{stage}"})
    item = resp.get("Item")
    if not item or "token" not in item:
        return None
    return item["token"]


def update_run_stage(
    table: Any,
    run_id: str,
    status: str,
    stage: str,
    ack_deadline: str,
    voice_url: Optional[str] = None,
    voice_key: Optional[str] = None,
) -> bool:
    """Set stage metadata (active_stage, ack_deadline, voice_url/key) conditionally."""
    run = get_run(table, run_id)
    if not run or run.get("status") in FINAL_STATUSES:
        return False

    run["status"] = status
    run["active_stage"] = stage
    run["ack_deadline"] = ack_deadline
    if voice_url is not None:
        run["voice_url"] = voice_url
    # The S3 object key outlives the presigned URL, which expires after an hour.
    # Storing it lets the API sign a fresh URL every time a run is read.
    if voice_key is not None:
        run["voice_key"] = voice_key

    try:
        table.update_item(
            Key={"PK": f"RUN#{run_id}", "SK": "META"},
            UpdateExpression="SET #d = :d, #s = :s",
            ConditionExpression="#s <> :ack AND #s <> :unack AND #s <> :fail",
            ExpressionAttributeNames={"#d": "data", "#s": "status"},
            ExpressionAttributeValues={
                ":d": to_ddb(run),
                ":s": status,
                ":ack": "ACKNOWLEDGED",
                ":unack": "UNACKNOWLEDGED",
                ":fail": "FAILED",
            },
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info("Run %s already closed, update_run_stage skipped.", run_id)
            return False
        raise


def set_run_status(
    table: Any,
    run_id: str,
    new_status: str,
    active_stage: Optional[str] = None,
    event_step: Optional[str] = None,
    event_detail: Optional[str] = None,
    allowed_from_statuses: Optional[List[str]] = None,
) -> bool:
    """Transition run to a new status conditionally if not already final."""
    run = get_run(table, run_id)
    if not run or run.get("status") in FINAL_STATUSES:
        return False

    if allowed_from_statuses and run.get("status") not in allowed_from_statuses:
        return False

    run["status"] = new_status
    run["active_stage"] = active_stage

    if event_step and event_detail:
        events = run.get("events", [])
        events.append({"ts": now_utc_iso(), "step": event_step, "detail": event_detail})
        run["events"] = events

    expr_attr_names = {"#d": "data", "#s": "status"}
    expr_attr_vals: Dict[str, Any] = {
        ":d": to_ddb(run),
        ":s": new_status,
    }

    if allowed_from_statuses:
        cond_terms = []
        for idx, st in enumerate(allowed_from_statuses):
            placeholder = f":allowed_{idx}"
            expr_attr_vals[placeholder] = st
            cond_terms.append(f"#s = {placeholder}")
        condition_expr = " OR ".join(cond_terms)
    else:
        condition_expr = "#s <> :ack AND #s <> :unack AND #s <> :fail"
        expr_attr_vals[":ack"] = "ACKNOWLEDGED"
        expr_attr_vals[":unack"] = "UNACKNOWLEDGED"
        expr_attr_vals[":fail"] = "FAILED"

    try:
        table.update_item(
            Key={"PK": f"RUN#{run_id}", "SK": "META"},
            UpdateExpression="SET #d = :d, #s = :s",
            ConditionExpression=condition_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_vals,
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info("Run %s status condition check failed, set_run_status skipped.", run_id)
            return False
        raise


def close_run_ack(
    table: Any,
    run_id: str,
    by: Optional[str] = None,
    via: str = "web",
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Acknowledge a run conditionally. Returns (True, updated_run) or (False, current_run)."""
    run = get_run(table, run_id)
    if not run:
        return False, None

    if run.get("status") in FINAL_STATUSES:
        return False, run

    now_ts = now_utc_iso()
    run["status"] = "ACKNOWLEDGED"
    run["acked_by"] = by or "Anonymous"
    run["acked_via"] = via
    active_stage = run.get("active_stage")
    run["active_stage"] = None

    events = run.get("events", [])
    detail_str = f"Acknowledged via {via} by {run['acked_by']}"
    events.append({"ts": now_ts, "step": "acknowledged", "detail": detail_str})
    run["events"] = events

    try:
        table.update_item(
            Key={"PK": f"RUN#{run_id}", "SK": "META"},
            UpdateExpression="SET #d = :d, #s = :s",
            ConditionExpression="#s <> :ack AND #s <> :unack AND #s <> :fail",
            ExpressionAttributeNames={"#d": "data", "#s": "status"},
            ExpressionAttributeValues={
                ":d": to_ddb(run),
                ":s": "ACKNOWLEDGED",
                ":ack": "ACKNOWLEDGED",
                ":unack": "UNACKNOWLEDGED",
                ":fail": "FAILED",
            },
        )
        return True, run
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            current = get_run(table, run_id)
            return False, current
        raise
