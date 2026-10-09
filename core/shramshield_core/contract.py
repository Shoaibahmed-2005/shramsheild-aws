"""Frozen contract constants and independent validators.

Standard library only. Everything here mirrors docs/BUILD_PLAN.md section 3.
The validators are deliberately written without using the engine: they are an
independent second opinion on whatever plan.py and friends produce.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "LEVELS",
    "WORKLOADS",
    "DISCLAIMER",
    "RUN_STATUSES",
    "RUN_STEPS",
    "LIMITS_C",
    "LEVEL_FOR_BAND",
    "MAX_WORK_MIN",
    "validate_site",
    "validate_plan",
    "validate_run",
    "validate_backtest",
]

LEVELS: list[str] = ["GREEN", "YELLOW", "ORANGE", "RED", "STOP"]

WORKLOADS: list[str] = ["light", "moderate", "heavy", "very_heavy"]

DISCLAIMER: str = (
    "Screening guidance estimated from weather-model data. It is not a measurement "
    "or medical advice. Use on-site judgement and stop work if anyone feels unwell."
)

RUN_STATUSES: list[str] = [
    "STARTED",
    "WAITING_ACK",
    "ESCALATED",
    "ACKNOWLEDGED",
    "UNACKNOWLEDGED",
    "FAILED",
]

RUN_STEPS: list[str] = [
    "plan_built",
    "voice_ready",
    "telegram_sent",
    "telegram_failed",
    "notified_primary",
    "escalated",
    "notified_backup",
    "acknowledged",
    "unacknowledged",
    "error",
]

# ACGIH 2026 TLV Table 1 as summarised by CCOHS. WBGT in degrees Celsius.
# None means the table lists no value ("--") for that band.
LIMITS_C: dict[str, dict[str, dict[str, float | None]]] = {
    "acclimatized": {
        "light": {"A": 31.0, "B": 31.0, "C": 32.0, "D": 32.5},
        "moderate": {"A": 28.0, "B": 29.0, "C": 30.0, "D": 31.5},
        "heavy": {"A": None, "B": 27.5, "C": 29.0, "D": 30.5},
        "very_heavy": {"A": None, "B": None, "C": 28.0, "D": 30.0},
    },
    "unacclimatized": {
        "light": {"A": 28.0, "B": 28.5, "C": 29.5, "D": 30.0},
        "moderate": {"A": 25.0, "B": 26.0, "C": 27.0, "D": 29.0},
        "heavy": {"A": None, "B": 24.0, "C": 25.5, "D": 28.0},
        "very_heavy": {"A": None, "B": None, "C": 24.5, "D": 27.0},
    },
}

LEVEL_FOR_BAND: dict[str, str] = {"A": "GREEN", "B": "YELLOW", "C": "ORANGE", "D": "RED"}

MAX_WORK_MIN: dict[str, int] = {"GREEN": 60, "YELLOW": 45, "ORANGE": 30, "RED": 15, "STOP": 0}

_BANDS: tuple[str, ...] = ("A", "B", "C", "D")
_SEVERITY: dict[str, int] = {level: i for i, level in enumerate(LEVELS)}
_SITE_ID_RE = re.compile(r"^[a-z0-9-]{3,20}$")
_PLAN_ID_RE = re.compile(r"^[a-z0-9-]{3,20}_\d{4}-\d{2}-\d{2}$")
_RUN_ID_RE = re.compile(r"^[a-z0-9-]{3,20}_\d{8}T\d{6}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
# WBGT values are carried to one decimal, so compare with a tolerance well below that.
_EPS = 1e-9


def _classify(wbgt_c: float, workload: str, acclimatized: bool) -> tuple[str, float | None]:
    """Independent re-implementation of the rule in contract section 3.7.

    Returns (level, limit_c). limit_c is None for STOP.
    """
    table = LIMITS_C["acclimatized" if acclimatized else "unacclimatized"][workload]
    for band in _BANDS:
        limit = table[band]
        if limit is not None and wbgt_c <= limit + _EPS:
            return LEVEL_FOR_BAND[band], limit
    return "STOP", None


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_contact(obj: Any, label: str, errors: list[str]) -> None:
    if not isinstance(obj, dict):
        errors.append(f"{label}: must be an object")
        return
    name = obj.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{label}.name: must be a non-empty string")
    chat_id = obj.get("telegram_chat_id", "__missing__")
    if chat_id == "__missing__":
        errors.append(f"{label}.telegram_chat_id: missing")
    elif not (chat_id is None or isinstance(chat_id, str) or (isinstance(chat_id, int) and not isinstance(chat_id, bool))):
        errors.append(f"{label}.telegram_chat_id: must be null, int or str")


def validate_site(obj: Any) -> list[str]:
    """Check a Site object against contract section 3.3."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["site: must be an object"]

    site_id = obj.get("site_id")
    if not isinstance(site_id, str) or not _SITE_ID_RE.match(site_id):
        errors.append("site_id: must match ^[a-z0-9-]{3,20}$")

    name = obj.get("name")
    if not isinstance(name, str) or not name:
        errors.append("name: must be a non-empty string")
    elif len(name) > 60:
        errors.append("name: at most 60 characters")

    lat = obj.get("lat")
    if not _is_num(lat):
        errors.append("lat: must be a number")
    elif not 6 <= lat <= 37:
        errors.append("lat: must be between 6 and 37 (India only)")

    lon = obj.get("lon")
    if not _is_num(lon):
        errors.append("lon: must be a number")
    elif not 68 <= lon <= 98:
        errors.append("lon: must be between 68 and 98 (India only)")

    if obj.get("workload") not in WORKLOADS:
        errors.append(f"workload: must be one of {WORKLOADS}")

    if not isinstance(obj.get("acclimatized"), bool):
        errors.append("acclimatized: must be true or false")

    start = obj.get("work_start_hour")
    end = obj.get("work_end_hour")
    start_ok = isinstance(start, int) and not isinstance(start, bool) and 0 <= start <= 23
    end_ok = isinstance(end, int) and not isinstance(end, bool) and 1 <= end <= 24
    if not start_ok:
        errors.append("work_start_hour: must be an integer 0 to 23")
    if not end_ok:
        errors.append("work_end_hour: must be an integer 1 to 24")
    if start_ok and end_ok and end <= start:
        errors.append("work_end_hour: must be greater than work_start_hour (end is exclusive)")

    if obj.get("language") not in ("hi", "en"):
        errors.append('language: must be "hi" or "en"')

    timeout = obj.get("ack_timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        errors.append("ack_timeout_seconds: must be an integer")
    elif not 30 <= timeout <= 3600:
        errors.append("ack_timeout_seconds: must be between 30 and 3600")

    _check_contact(obj.get("supervisor"), "supervisor", errors)
    _check_contact(obj.get("backup"), "backup", errors)

    return errors


def _plan_hour_errors(
    hour_obj: Any,
    index: int,
    date: str,
    workload: str,
    acclimatized: bool,
) -> list[str]:
    """Check one entry of plan["hours"] against sections 3.4 and 3.7."""
    where = f"hours[{index}]"
    if not isinstance(hour_obj, dict):
        return [f"{where}: must be an object"]

    errors: list[str] = []
    hour = hour_obj.get("hour")
    if hour != index:
        errors.append(f"{where}.hour: expected {index}, got {hour!r}")

    expected_time = f"{date}T{index:02d}:00"
    if hour_obj.get("time") != expected_time:
        errors.append(f"{where}.time: expected {expected_time!r}, got {hour_obj.get('time')!r}")

    if not isinstance(hour_obj.get("in_work_hours"), bool):
        errors.append(f"{where}.in_work_hours: must be true or false")

    level = hour_obj.get("level")
    wbgt = hour_obj.get("wbgt_c")

    if level == "UNKNOWN":
        if wbgt is not None:
            errors.append(f"{where}.wbgt_c: must be null when level is UNKNOWN")
        for field in ("max_work_min", "min_rest_min", "limit_c"):
            if hour_obj.get(field, "__missing__") is not None:
                errors.append(f"{where}.{field}: must be null when level is UNKNOWN")
        reason = hour_obj.get("reason")
        if not isinstance(reason, str) or "missing" not in reason.lower():
            errors.append(f"{where}.reason: must say the data was missing")
        return errors

    if level not in LEVELS:
        errors.append(f"{where}.level: must be one of {LEVELS} or UNKNOWN, got {level!r}")
        return errors

    if hour_obj.get("wbgt_method") not in ("liljegren", "simple_fallback"):
        errors.append(f"{where}.wbgt_method: must be liljegren or simple_fallback")

    if not isinstance(hour_obj.get("reason"), str) or not hour_obj.get("reason"):
        errors.append(f"{where}.reason: must be a non-empty string")

    if not _is_num(wbgt):
        errors.append(f"{where}.wbgt_c: must be a number when level is not UNKNOWN")
        return errors

    expected_work = MAX_WORK_MIN[level]
    if hour_obj.get("max_work_min") != expected_work:
        errors.append(
            f"{where}.max_work_min: level {level} requires {expected_work}, "
            f"got {hour_obj.get('max_work_min')!r}"
        )
    if hour_obj.get("min_rest_min") != 60 - expected_work:
        errors.append(
            f"{where}.min_rest_min: level {level} requires {60 - expected_work}, "
            f"got {hour_obj.get('min_rest_min')!r}"
        )

    expected_level, expected_limit = _classify(float(wbgt), workload, acclimatized)
    if level != expected_level:
        state = "acclimatized" if acclimatized else "unacclimatized"
        errors.append(
            f"{where}.level: WBGT {wbgt} C with {workload} work ({state}) "
            f"classifies as {expected_level}, got {level}"
        )
    limit = hour_obj.get("limit_c")
    if expected_limit is None:
        if limit is not None:
            errors.append(f"{where}.limit_c: must be null for {expected_level}")
    elif not _is_num(limit) or abs(float(limit) - expected_limit) > 1e-6:
        errors.append(f"{where}.limit_c: expected {expected_limit}, got {limit!r}")

    return errors


def _expected_windows(hours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Runs of consecutive work hours sharing one level, GREEN and UNKNOWN excluded."""
    windows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for hour_obj in hours:
        level = hour_obj.get("level")
        eligible = bool(hour_obj.get("in_work_hours")) and level in LEVELS and level != "GREEN"
        if not eligible:
            current = None
            continue
        index = hour_obj.get("hour")
        if current is not None and current["level"] == level and current["end_hour"] == index:
            current["end_hour"] = index + 1
            continue
        current = {
            "start_hour": index,
            "end_hour": index + 1,
            "level": level,
            "max_work_min": MAX_WORK_MIN[level],
            "min_rest_min": 60 - MAX_WORK_MIN[level],
        }
        windows.append(current)
    return windows


def _summary_errors(summary: Any, hours: list[dict[str, Any]]) -> list[str]:
    """Check plan["summary"] is consistent with plan["hours"]."""
    if not isinstance(summary, dict):
        return ["summary: must be an object"]

    errors: list[str] = []
    work_hours = [h for h in hours if isinstance(h, dict) and h.get("in_work_hours")]
    rated = [h for h in work_hours if h.get("level") in LEVELS]

    if not rated:
        if summary.get("worst_level") != "UNKNOWN":
            errors.append("summary.worst_level: must be UNKNOWN when every work hour is UNKNOWN")
        if summary.get("peak_wbgt_c") is not None:
            errors.append("summary.peak_wbgt_c: must be null when every work hour is UNKNOWN")
        if summary.get("peak_hour") is not None:
            errors.append("summary.peak_hour: must be null when every work hour is UNKNOWN")
        if summary.get("windows") != []:
            errors.append("summary.windows: must be empty when every work hour is UNKNOWN")
        return errors

    expected_worst = max((h["level"] for h in rated), key=lambda level: _SEVERITY[level])
    if summary.get("worst_level") != expected_worst:
        errors.append(
            f"summary.worst_level: expected {expected_worst}, got {summary.get('worst_level')!r}"
        )

    measured = [h for h in work_hours if _is_num(h.get("wbgt_c"))]
    if measured:
        peak = max(measured, key=lambda h: (float(h["wbgt_c"]), -int(h["hour"])))
        reported_peak = summary.get("peak_wbgt_c")
        if not _is_num(reported_peak) or abs(float(reported_peak) - float(peak["wbgt_c"])) > 1e-6:
            errors.append(
                f"summary.peak_wbgt_c: expected {peak['wbgt_c']}, got {reported_peak!r}"
            )
        if summary.get("peak_hour") != peak["hour"]:
            errors.append(
                f"summary.peak_hour: expected {peak['hour']}, got {summary.get('peak_hour')!r}"
            )

    expected = _expected_windows([h for h in hours if isinstance(h, dict)])
    if summary.get("windows") != expected:
        errors.append(f"summary.windows: expected {expected}, got {summary.get('windows')!r}")

    return errors


def validate_plan(obj: Any) -> list[str]:
    """Check a Plan object against contract sections 3.4, 3.7 and 3.2."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["plan: must be an object"]

    site_id = obj.get("site_id")
    if not isinstance(site_id, str) or not _SITE_ID_RE.match(site_id):
        errors.append("site_id: must match ^[a-z0-9-]{3,20}$")

    date = obj.get("date")
    if not isinstance(date, str) or not _DATE_RE.match(date):
        errors.append("date: must look like YYYY-MM-DD")

    plan_id = obj.get("plan_id")
    if not isinstance(plan_id, str) or not _PLAN_ID_RE.match(plan_id):
        errors.append("plan_id: must look like site_id_YYYY-MM-DD")
    elif isinstance(site_id, str) and isinstance(date, str) and plan_id != f"{site_id}_{date}":
        errors.append(f"plan_id: expected {site_id}_{date}, got {plan_id}")

    generated_at = obj.get("generated_at")
    if not isinstance(generated_at, str) or not _TS_RE.match(generated_at):
        errors.append("generated_at: must be a UTC timestamp ending with Z")

    source = obj.get("source")
    if not isinstance(source, dict):
        errors.append("source: must be an object")
    else:
        for field in ("weather", "wbgt_method", "thermofeel"):
            if not isinstance(source.get(field), str) or not source.get(field):
                errors.append(f"source.{field}: must be a non-empty string")

    profile = obj.get("profile")
    workload: str | None = None
    acclimatized: bool | None = None
    if not isinstance(profile, dict):
        errors.append("profile: must be an object")
    else:
        if profile.get("workload") in WORKLOADS:
            workload = profile["workload"]
        else:
            errors.append(f"profile.workload: must be one of {WORKLOADS}")
        if isinstance(profile.get("acclimatized"), bool):
            acclimatized = profile["acclimatized"]
        else:
            errors.append("profile.acclimatized: must be true or false")

    hours = obj.get("hours")
    if not isinstance(hours, list):
        errors.append("hours: must be a list of 24 entries")
    else:
        if len(hours) != 24:
            errors.append(f"hours: must have 24 entries, got {len(hours)}")
        hour_errors: list[str] = []
        if workload is not None and acclimatized is not None and isinstance(date, str):
            for index, hour_obj in enumerate(hours):
                hour_errors.extend(
                    _plan_hour_errors(hour_obj, index, date, workload, acclimatized)
                )
        errors.extend(hour_errors)
        # The summary is derived from the hours, so only check it once the hours
        # themselves are sound; otherwise every hour error would echo twice.
        if not hour_errors and len(hours) == 24:
            errors.extend(_summary_errors(obj.get("summary"), hours))

    messages = obj.get("messages")
    if not isinstance(messages, dict):
        errors.append("messages: must be an object with en and hi")
    else:
        for lang in ("en", "hi"):
            if not isinstance(messages.get(lang), str) or not messages.get(lang):
                errors.append(f"messages.{lang}: must be a non-empty string")

    if obj.get("disclaimer") != DISCLAIMER:
        errors.append("disclaimer: must be the exact text from contract section 3.2")

    return errors


def validate_run(obj: Any) -> list[str]:
    """Check a Run object against contract section 3.5."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["run: must be an object"]

    run_id = obj.get("run_id")
    if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id):
        errors.append("run_id: must look like site_id_YYYYMMDDTHHMMSS")

    site_id = obj.get("site_id")
    if not isinstance(site_id, str) or not _SITE_ID_RE.match(site_id):
        errors.append("site_id: must match ^[a-z0-9-]{3,20}$")

    plan_id = obj.get("plan_id")
    if not isinstance(plan_id, str) or not _PLAN_ID_RE.match(plan_id):
        errors.append("plan_id: must look like site_id_YYYY-MM-DD")

    status = obj.get("status")
    if status not in RUN_STATUSES:
        errors.append(f"status: must be one of {RUN_STATUSES}")

    stage = obj.get("active_stage", "__missing__")
    if stage == "__missing__":
        errors.append("active_stage: missing")
    elif stage not in ("primary", "backup", None):
        errors.append("active_stage: must be primary, backup or null")
    elif status in ("ACKNOWLEDGED", "UNACKNOWLEDGED", "FAILED") and stage is not None:
        errors.append(f"active_stage: must be null for the final status {status}")

    created_at = obj.get("created_at")
    if not isinstance(created_at, str) or not _TS_RE.match(created_at):
        errors.append("created_at: must be a UTC timestamp ending with Z")

    deadline = obj.get("ack_deadline", "__missing__")
    if deadline == "__missing__":
        errors.append("ack_deadline: missing")
    elif deadline is not None and not (isinstance(deadline, str) and _TS_RE.match(deadline)):
        errors.append("ack_deadline: must be null or a UTC timestamp ending with Z")

    voice_url = obj.get("voice_url", "__missing__")
    if voice_url == "__missing__":
        errors.append("voice_url: missing")
    elif voice_url is not None and not isinstance(voice_url, str):
        errors.append("voice_url: must be null or a string")

    acked_by = obj.get("acked_by", "__missing__")
    if acked_by == "__missing__":
        errors.append("acked_by: missing")
    elif acked_by is not None and not isinstance(acked_by, str):
        errors.append("acked_by: must be null or a string")

    acked_via = obj.get("acked_via", "__missing__")
    if acked_via == "__missing__":
        errors.append("acked_via: missing")
    elif acked_via not in ("telegram", "web", None):
        errors.append("acked_via: must be telegram, web or null")

    events = obj.get("events")
    if not isinstance(events, list):
        errors.append("events: must be a list")
    else:
        for index, event in enumerate(events):
            where = f"events[{index}]"
            if not isinstance(event, dict):
                errors.append(f"{where}: must be an object")
                continue
            ts = event.get("ts")
            if not isinstance(ts, str) or not _TS_RE.match(ts):
                errors.append(f"{where}.ts: must be a UTC timestamp ending with Z")
            if event.get("step") not in RUN_STEPS:
                errors.append(f"{where}.step: must be one of {RUN_STEPS}")
            if not isinstance(event.get("detail"), str):
                errors.append(f"{where}.detail: must be a string")

    return errors


def _threshold_errors(entry: Any, where: str, dangerous_hours: Any) -> list[str]:
    """Check one by_threshold entry: caught + missed must equal dangerous_hours."""
    if not isinstance(entry, dict):
        return [f"{where}: must be an object"]

    errors: list[str] = []
    for field in ("threshold_c", "alert_hours", "caught", "missed", "false_alarm_hours"):
        if not _is_num(entry.get(field)):
            errors.append(f"{where}.{field}: must be a number")
    if not _is_num(entry.get("missed_pct")):
        errors.append(f"{where}.missed_pct: must be a number")

    if errors:
        return errors

    if _is_num(dangerous_hours) and entry["caught"] + entry["missed"] != dangerous_hours:
        errors.append(
            f"{where}: caught ({entry['caught']}) + missed ({entry['missed']}) "
            f"must equal dangerous_hours ({dangerous_hours})"
        )

    if _is_num(dangerous_hours):
        expected_pct = 0.0 if dangerous_hours == 0 else 100.0 * entry["missed"] / dangerous_hours
        # Allow the value to be stored rounded to one decimal, as the contract example shows.
        if abs(float(entry["missed_pct"]) - expected_pct) > 0.05 + 1e-9:
            errors.append(
                f"{where}.missed_pct: expected about {expected_pct:.1f}, got {entry['missed_pct']}"
            )

    return errors


def validate_backtest(obj: Any) -> list[str]:
    """Check a Backtest object against contract section 3.13."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["backtest: must be an object"]

    for key in (
        "generated_at",
        "period",
        "profile",
        "dangerous_levels",
        "baseline_thresholds_c",
        "sites",
        "totals",
        "caveats",
        "sources",
    ):
        if key not in obj:
            errors.append(f"{key}: missing")
    if errors:
        return errors

    if not isinstance(obj["generated_at"], str) or not _TS_RE.match(obj["generated_at"]):
        errors.append("generated_at: must be a UTC timestamp ending with Z")

    period = obj["period"]
    if not isinstance(period, dict):
        errors.append("period: must be an object")
    else:
        for field in ("start", "end"):
            if not isinstance(period.get(field), str) or not _DATE_RE.match(period[field]):
                errors.append(f"period.{field}: must look like YYYY-MM-DD")

    profile = obj["profile"]
    if not isinstance(profile, dict):
        errors.append("profile: must be an object")
    else:
        if profile.get("workload") not in WORKLOADS:
            errors.append(f"profile.workload: must be one of {WORKLOADS}")
        if not isinstance(profile.get("acclimatized"), bool):
            errors.append("profile.acclimatized: must be true or false")
        for field in ("work_start_hour", "work_end_hour"):
            if not isinstance(profile.get(field), int) or isinstance(profile.get(field), bool):
                errors.append(f"profile.{field}: must be an integer")

    if obj["dangerous_levels"] != ["RED", "STOP"]:
        errors.append('dangerous_levels: must be ["RED", "STOP"]')

    thresholds = obj["baseline_thresholds_c"]
    if not isinstance(thresholds, list) or not thresholds or not all(_is_num(t) for t in thresholds):
        errors.append("baseline_thresholds_c: must be a non-empty list of numbers")

    if not isinstance(obj["caveats"], list) or not all(
        isinstance(c, str) and c for c in obj["caveats"]
    ):
        errors.append("caveats: must be a list of non-empty strings")

    sources = obj["sources"]
    if not isinstance(sources, dict):
        errors.append("sources: must be an object")
    else:
        for field in ("weather", "wbgt_method", "thermofeel"):
            if not isinstance(sources.get(field), str) or not sources.get(field):
                errors.append(f"sources.{field}: must be a non-empty string")

    sites = obj["sites"]
    if not isinstance(sites, list) or not sites:
        errors.append("sites: must be a non-empty list")
    else:
        for index, site in enumerate(sites):
            errors.extend(_backtest_site_errors(site, f"sites[{index}]"))

    totals = obj["totals"]
    if not isinstance(totals, dict):
        errors.append("totals: must be an object")
    else:
        if not _is_num(totals.get("dangerous_hours")):
            errors.append("totals.dangerous_hours: must be a number")
        by_threshold = totals.get("by_threshold")
        if not isinstance(by_threshold, list) or not by_threshold:
            errors.append("totals.by_threshold: must be a non-empty list")
        else:
            for index, entry in enumerate(by_threshold):
                errors.extend(
                    _threshold_errors(
                        entry, f"totals.by_threshold[{index}]", totals.get("dangerous_hours")
                    )
                )

    return errors


def _backtest_site_errors(site: Any, where: str) -> list[str]:
    """Check one entry of backtest["sites"], including the counting identities."""
    if not isinstance(site, dict):
        return [f"{where}: must be an object"]

    errors: list[str] = []
    site_id = site.get("site_id")
    if not isinstance(site_id, str) or not _SITE_ID_RE.match(site_id):
        errors.append(f"{where}.site_id: must match ^[a-z0-9-]{{3,20}}$")
    if not isinstance(site.get("name"), str) or not site.get("name"):
        errors.append(f"{where}.name: must be a non-empty string")
    for field in ("lat", "lon", "work_hours_total", "work_hours_with_data", "dangerous_hours"):
        if not _is_num(site.get(field)):
            errors.append(f"{where}.{field}: must be a number")

    level_counts = site.get("level_counts")
    if not isinstance(level_counts, dict):
        errors.append(f"{where}.level_counts: must be an object")
    elif sorted(level_counts) != sorted(LEVELS):
        errors.append(f"{where}.level_counts: must have exactly the keys {LEVELS}")
    elif not all(_is_num(v) for v in level_counts.values()):
        errors.append(f"{where}.level_counts: values must be numbers")
    elif _is_num(site.get("work_hours_with_data")):
        total = sum(level_counts.values())
        if total != site["work_hours_with_data"]:
            errors.append(
                f"{where}.level_counts: sum ({total}) must equal "
                f"work_hours_with_data ({site['work_hours_with_data']})"
            )

    by_threshold = site.get("by_threshold")
    if not isinstance(by_threshold, list) or not by_threshold:
        errors.append(f"{where}.by_threshold: must be a non-empty list")
    else:
        for index, entry in enumerate(by_threshold):
            errors.extend(
                _threshold_errors(
                    entry, f"{where}.by_threshold[{index}]", site.get("dangerous_hours")
                )
            )

    example = site.get("example_hour", "__missing__")
    if example == "__missing__":
        errors.append(f"{where}.example_hour: missing")
    elif example is not None:
        if not isinstance(example, dict):
            errors.append(f"{where}.example_hour: must be null or an object")
        else:
            for field in ("time", "air_temp_c", "rh_pct", "wbgt_c", "level"):
                if field not in example:
                    errors.append(f"{where}.example_hour.{field}: missing")
            if example.get("level") not in LEVELS:
                errors.append(f"{where}.example_hour.level: must be one of {LEVELS}")

    return errors
