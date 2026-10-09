"""Build a day plan for one site (contract section 3.4)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import thermofeel

from . import weather
from .contract import DISCLAIMER, LEVELS
from .limits import classify
from .messages import build_messages
from .wbgt import IST_OFFSET, compute_wbgt

__all__ = ["build_plan", "build_plan_for_site", "india_today"]

_SEVERITY = {level: index for index, level in enumerate(LEVELS)}


def india_today(now_utc: datetime | None = None) -> str:
    """Today's date in India time as YYYY-MM-DD."""
    moment = now_utc or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return (moment + IST_OFFSET).strftime("%Y-%m-%d")


def _round_or_none(value: Any, digits: int) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(round(float(value)))


def _build_hour(
    row: dict[str, Any],
    hour: int,
    date_str: str,
    site: dict[str, Any],
) -> dict[str, Any]:
    wbgt_c, method = compute_wbgt(row, site["lat"], site["lon"])
    band = classify(wbgt_c, site["workload"], site["acclimatized"])
    return {
        "hour": hour,
        "time": f"{date_str}T{hour:02d}:00",
        "in_work_hours": site["work_start_hour"] <= hour < site["work_end_hour"],
        "air_temp_c": _round_or_none(row.get("air_temp_c"), 1),
        "rh_pct": _int_or_none(row.get("rh_pct")),
        "wind_ms": _round_or_none(row.get("wind_ms"), 1),
        "ghi_wm2": _int_or_none(row.get("ghi_wm2")),
        "wbgt_c": wbgt_c,
        "wbgt_method": method,
        "level": band["level"],
        "max_work_min": band["max_work_min"],
        "min_rest_min": band["min_rest_min"],
        "limit_c": band["limit_c"],
        "reason": band["reason"],
    }


def _windows(hours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Runs of consecutive work hours sharing one level, GREEN and UNKNOWN excluded."""
    windows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for hour in hours:
        level = hour["level"]
        if not (hour["in_work_hours"] and level in LEVELS and level != "GREEN"):
            current = None
            continue
        if current is not None and current["level"] == level and current["end_hour"] == hour["hour"]:
            current["end_hour"] = hour["hour"] + 1
            continue
        current = {
            "start_hour": hour["hour"],
            "end_hour": hour["hour"] + 1,
            "level": level,
            "max_work_min": hour["max_work_min"],
            "min_rest_min": hour["min_rest_min"],
        }
        windows.append(current)
    return windows


def _summary(hours: list[dict[str, Any]]) -> dict[str, Any]:
    work_hours = [hour for hour in hours if hour["in_work_hours"]]
    rated = [hour for hour in work_hours if hour["level"] in LEVELS]

    if not rated:
        return {
            "worst_level": "UNKNOWN",
            "peak_wbgt_c": None,
            "peak_hour": None,
            "windows": [],
        }

    worst = max((hour["level"] for hour in rated), key=lambda level: _SEVERITY[level])
    measured = [hour for hour in work_hours if hour["wbgt_c"] is not None]
    peak = max(measured, key=lambda hour: (hour["wbgt_c"], -hour["hour"]))
    return {
        "worst_level": worst,
        "peak_wbgt_c": peak["wbgt_c"],
        "peak_hour": peak["hour"],
        "windows": _windows(hours),
    }


def build_plan(
    site: dict[str, Any],
    rows: list[dict[str, Any]],
    date_str: str,
    generated_at: str,
    *,
    weather_source: str = "open-meteo",
) -> dict[str, Any]:
    """Turn 24 hourly weather rows into a plan object.

    ``generated_at`` is supplied by the caller so tests stay deterministic.
    """
    if len(rows) != 24:
        raise ValueError(f"build_plan needs exactly 24 rows, got {len(rows)}")

    hours = [_build_hour(row, index, date_str, site) for index, row in enumerate(rows)]
    summary = _summary(hours)

    methods = Counter(hour["wbgt_method"] for hour in hours if hour["wbgt_method"])
    source: dict[str, Any] = {
        "weather": weather_source,
        "wbgt_method": methods.most_common(1)[0][0] if methods else "none",
        "thermofeel": thermofeel.__version__,
    }
    fallback_hours = methods.get("simple_fallback", 0)
    if fallback_hours:
        source["simple_fallback_hours"] = fallback_hours

    return {
        "plan_id": f"{site['site_id']}_{date_str}",
        "site_id": site["site_id"],
        "date": date_str,
        "generated_at": generated_at,
        "source": source,
        "profile": {"workload": site["workload"], "acclimatized": site["acclimatized"]},
        "hours": hours,
        "summary": summary,
        "messages": build_messages(site, summary, hours),
        "disclaimer": DISCLAIMER,
    }


def build_plan_for_site(
    site: dict[str, Any],
    *,
    now_utc: datetime | None = None,
    date_str: str | None = None,
    fetch: Callable[..., dict[str, Any]] = weather.fetch_forecast,
) -> dict[str, Any]:
    """Fetch the forecast and build today's plan: one call for the backend."""
    target_date = date_str or india_today(now_utc)
    response = fetch(site["lat"], site["lon"])
    rows = weather.rows_for_date(weather.parse_hourly(response), target_date)
    generated_at = (now_utc or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return build_plan(site, rows, target_date, generated_at)
