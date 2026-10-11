"""Step Functions Notify Lambda task.

Stores Task Tokens, generates Polly voice messages, sends Telegram alerts
with inline acknowledgement buttons, and manages stage escalation state.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from typing import Any, Dict, Optional

import boto3

try:
    from common import db, runs, telegram, voice
except ImportError:
    from src.common import db, runs, telegram, voice

logger = logging.getLogger("notify")
logger.setLevel(logging.INFO)

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))


def _get_sfn_client() -> Any:
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
    return boto3.client("stepfunctions", region_name=region)


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
    """Lambda entry point for Step Functions waitForTaskToken notification task."""
    action = event.get("action", "notify")
    stage = event.get("stage", "primary")  # "primary" or "backup"
    run_id = event.get("run_id")
    site_id = event.get("site_id")
    token = event.get("token")

    if not run_id or not site_id or not token:
        logger.error("Missing required parameters in notify event: %s", event)
        return {"error": "Missing run_id, site_id, or token"}

    table = _get_table()
    sfn = _get_sfn_client()

    # a. Load run and site. If run is already final, complete workflow step immediately.
    run = runs.get_run(table, run_id)
    site = db.get_site(table, site_id)

    if not run or run.get("status") in runs.FINAL_STATUSES:
        logger.info("Run %s is already final (%s). Calling send_task_success immediately.", run_id, run.get("status") if run else "None")
        try:
            sfn.send_task_success(taskToken=token, output="{}")
        except Exception as exc:
            logger.warning("Error calling send_task_success on final run: %s", exc)
        return {"status": "already_final"}

    if not site:
        logger.error("Site %s not found for run %s", site_id, run_id)
        runs.add_event(table, run_id, "error", f"Site {site_id} not found")
        sfn.send_task_failure(taskToken=token, error="SiteNotFound", cause=f"Site {site_id} not found")
        return {"error": "Site not found"}

    # b. Store task token with TTL 7200s
    runs.save_token(table, run_id, stage, token, ttl_seconds=7200)

    # c. Chat id check
    contact_key = "supervisor" if stage == "primary" else "backup"
    contact = site.get(contact_key) or {}
    chat_id = contact.get("telegram_chat_id")

    if not chat_id:
        if stage == "primary":
            logger.warning("No chat ID configured for primary contact on site %s", site_id)
            runs.add_event(table, run_id, "telegram_failed", "no chat id configured for primary")
            sfn.send_task_failure(taskToken=token, error="NoChatId", cause="no chat id configured for primary")
            return {"status": "failed_no_chat_id"}
        else:
            logger.info("No chat ID configured for backup contact on site %s. Triggering NoBackup.", site_id)
            sfn.send_task_failure(taskToken=token, error="NoBackup", cause="no chat id configured for backup")
            return {"status": "skipped_no_backup"}

    # d. Plan and message composition
    plan_id = run.get("plan_id", "")
    date_part = plan_id.split("_")[-1] if "_" in plan_id else datetime.now(INDIA_TZ).strftime("%Y-%m-%d")
    plan = db.get_cached_plan(table, site_id, date_part)

    if not plan:
        try:
            from shramshield_core.plan import build_plan_for_site
        except ImportError:
            from src.shramshield_core.plan import build_plan_for_site
        plan = build_plan_for_site(site, date_str=date_part)

    lang = site.get("language", "hi")
    msg_body = plan.get("messages", {}).get(lang) or plan.get("messages", {}).get("hi") or ""

    dashboard_url = os.environ.get("DASHBOARD_URL", "").rstrip("/")
    lines = [msg_body, f"Run {run_id}"]
    if dashboard_url:
        lines.append(f"{dashboard_url}/#/run/{run_id}")
    disclaimer = plan.get("disclaimer")
    if disclaimer:
        lines.append(disclaimer)

    telegram_text = "\n".join(lines)

    # e. Voice synthesis
    voice_url = run.get("voice_url")
    if stage == "primary" and not voice_url:
        try:
            voice_url = voice.synthesize(msg_body, run_id, lang=lang)
            runs.add_event(table, run_id, "voice_ready", "Hindi voice message ready" if lang == "hi" else "Voice message ready")
        except Exception as exc:
            logger.error("Polly synthesis error: %s", exc)
            runs.add_event(table, run_id, "error", type(exc).__name__)
            voice_url = None
    elif stage == "backup" and not voice_url:
        try:
            voice_url = voice.synthesize(msg_body, run_id, lang=lang)
        except Exception as exc:
            logger.warning("Polly backup synthesis skipped: %s", exc)
            voice_url = None

    # f. Send Telegram message with inline acknowledge button
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Acknowledge / मिल गया", "callback_data": f"ack:{run_id}"}
            ]
        ]
    }

    try:
        telegram.send_message(chat_id, telegram_text, reply_markup=reply_markup)
    except Exception as exc:
        logger.error("Telegram message delivery failed: %s", exc)
        runs.add_event(table, run_id, "telegram_failed", "text delivery failed")
        sfn.send_task_failure(taskToken=token, error="TelegramDeliveryFailed", cause=str(exc))
        return {"status": "telegram_failed"}

    # Send audio if available
    if voice_url:
        try:
            telegram.send_audio(chat_id, voice_url, caption="🔊 Voice safety message", title="ShramShield Voice")
        except Exception as exc:
            logger.warning("Voice audio delivery failed (text succeeded): %s", exc)
            runs.add_event(table, run_id, "telegram_failed", "voice not delivered")

    # g. Update run state & events
    event_notified = "notified_primary" if stage == "primary" else "notified_backup"
    contact_name = contact.get("name") or ("Supervisor" if stage == "primary" else "Backup")
    runs.add_event(table, run_id, "telegram_sent", f"plan sent to {contact_name}")
    runs.add_event(table, run_id, event_notified, "waiting for acknowledgement")

    # Compute ack deadline
    timeout_secs = int(site.get("ack_timeout_seconds", 900))
    deadline_ts = (datetime.now(timezone.utc) + timedelta(seconds=timeout_secs)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Set status: primary -> WAITING_ACK (ESCALATED is set by record.py when moving to backup)
    target_status = "WAITING_ACK" if stage == "primary" else "ESCALATED"
    runs.update_run_stage(table, run_id, target_status, stage, deadline_ts, voice_url=voice_url)

    logger.info("Stage %s notification completed for run %s. Waiting for acknowledgement.", stage, run_id)
    # Return WITHOUT calling send_task_success so Step Functions waits for task token
    return {"status": "waiting_ack", "stage": stage}
