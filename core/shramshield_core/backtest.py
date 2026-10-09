"""Backtest: WBGT levels against a plain air-temperature alert (contract 3.13).

A dangerous hour is a work hour whose level is RED or STOP. A baseline alert
hour is a work hour whose air temperature is at or above the threshold. This
compares two methods on the same historical weather; it says nothing about
heat illness cases.
"""

from __future__ import annotations

from typing import Any

from .contract import LEVELS
from .limits import classify
from .wbgt import compute_wbgt

__all__ = [
    "DANGEROUS_LEVELS",
    "DEFAULT_THRESHOLDS_C",
    "WIND_FLOOR_MS",
    "REQUIRED_CAVEATS",
    "rate_hours",
    "backtest_site",
    "combine_totals",
    "threshold_row",
]

DANGEROUS_LEVELS: tuple[str, ...] = ("RED", "STOP")
DEFAULT_THRESHOLDS_C: tuple[int, ...] = (37, 40, 42)

# Liljegren raises any 10 m wind below this to the floor before solving the
# globe energy balance, so at or under it the convective cooling term is
# saturated and WBGT can legitimately run well above air temperature.
WIND_FLOOR_MS = 0.62

REQUIRED_CAVEATS: tuple[str, ...] = (
    "Compares two methods on the same historical data; it is not validated against heat illness cases.",
    "Uses historical reanalysis data, not archived forecasts, so real-time forecast error is not included.",
    "WBGT is estimated from modelled weather at a city point, not measured at the worksite.",
    "Screening limits are for an 8-hour workday and are not a prescription of work and rest periods.",
)


def rate_hours(
    rows: list[dict[str, Any]],
    lat: float,
    lon: float,
    *,
    workload: str,
    acclimatized: bool,
) -> list[dict[str, Any]]:
    """Add wbgt_c, wbgt_method and level to every row, work hour or not."""
    rated = []
    for row in rows:
        wbgt_c, method = compute_wbgt(row, lat, lon)
        band = classify(wbgt_c, workload, acclimatized)
        rated.append(
            {
                **row,
                "hour": int(str(row["time"])[11:13]),
                "wbgt_c": wbgt_c,
                "wbgt_method": method,
                "level": band["level"],
            }
        )
    return rated


def threshold_row(
    threshold_c: float,
    work_hours: list[dict[str, Any]],
    dangerous_hours: int,
) -> dict[str, Any]:
    """One by_threshold entry as defined in contract 3.13."""
    alert = [
        hour
        for hour in work_hours
        if hour["air_temp_c"] is not None and hour["air_temp_c"] >= threshold_c
    ]
    caught = sum(1 for hour in alert if hour["level"] in DANGEROUS_LEVELS)
    missed = dangerous_hours - caught
    false_alarms = sum(1 for hour in alert if hour["level"] in ("GREEN", "YELLOW"))
    missed_pct = 0.0 if dangerous_hours == 0 else round(100.0 * missed / dangerous_hours, 1)
    return {
        "threshold_c": threshold_c,
        "alert_hours": len(alert),
        "caught": caught,
        "missed": missed,
        "missed_pct": missed_pct,
        "false_alarm_hours": false_alarms,
    }


def backtest_site(
    site: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    workload: str,
    acclimatized: bool,
    work_start_hour: int,
    work_end_hour: int,
    thresholds_c: tuple[int, ...] | list[int] = DEFAULT_THRESHOLDS_C,
) -> dict[str, Any]:
    """One entry of backtest["sites"] for a whole period of hourly rows."""
    rated = rate_hours(
        rows, site["lat"], site["lon"], workload=workload, acclimatized=acclimatized
    )
    work_hours = [
        hour for hour in rated if work_start_hour <= hour["hour"] < work_end_hour
    ]

    level_counts = {level: 0 for level in LEVELS}
    for hour in work_hours:
        if hour["level"] in level_counts:
            level_counts[hour["level"]] += 1

    with_data = sum(level_counts.values())
    dangerous = sum(level_counts[level] for level in DANGEROUS_LEVELS)

    dangerous_rows = [hour for hour in work_hours if hour["level"] in DANGEROUS_LEVELS]
    example_hour = None
    if dangerous_rows:
        coolest = min(
            (hour for hour in dangerous_rows if hour["air_temp_c"] is not None),
            key=lambda hour: (hour["air_temp_c"], hour["time"]),
            default=None,
        )
        if coolest is not None:
            example_hour = {
                "time": coolest["time"],
                "air_temp_c": round(float(coolest["air_temp_c"]), 1),
                "rh_pct": int(round(float(coolest["rh_pct"]))),
                "wbgt_c": coolest["wbgt_c"],
                "level": coolest["level"],
            }

    return {
        "site_id": site["site_id"],
        "name": site["name"],
        "lat": site["lat"],
        "lon": site["lon"],
        "work_hours_total": len(work_hours),
        "work_hours_with_data": with_data,
        "level_counts": level_counts,
        "dangerous_hours": dangerous,
        "by_threshold": [
            threshold_row(threshold, work_hours, dangerous) for threshold in thresholds_c
        ],
        "example_hour": example_hour,
    }


def combine_totals(
    sites: list[dict[str, Any]],
    thresholds_c: tuple[int, ...] | list[int] = DEFAULT_THRESHOLDS_C,
) -> dict[str, Any]:
    """Sum the per-site counts into the totals block."""
    total_dangerous = sum(site["dangerous_hours"] for site in sites)
    rows = []
    for index, threshold in enumerate(thresholds_c):
        entries = [site["by_threshold"][index] for site in sites]
        caught = sum(entry["caught"] for entry in entries)
        missed = sum(entry["missed"] for entry in entries)
        rows.append(
            {
                "threshold_c": threshold,
                "alert_hours": sum(entry["alert_hours"] for entry in entries),
                "caught": caught,
                "missed": missed,
                "missed_pct": (
                    0.0 if total_dangerous == 0 else round(100.0 * missed / total_dangerous, 1)
                ),
                "false_alarm_hours": sum(entry["false_alarm_hours"] for entry in entries),
            }
        )
    return {"dangerous_hours": total_dangerous, "by_threshold": rows}
