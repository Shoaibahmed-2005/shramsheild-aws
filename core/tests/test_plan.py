"""Plan building on hand-made rows, no network (task P1.1 step 10).

Every plan produced here must pass contract.validate_plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from shramshield_core.contract import validate_plan
from shramshield_core.plan import build_plan, build_plan_for_site, india_today

DATE = "2026-05-15"
GENERATED_AT = "2026-05-15T00:30:00Z"


def site(**overrides: Any) -> dict[str, Any]:
    base = {
        "site_id": "chn-01",
        "name": "Chennai demo site",
        "lat": 13.085,
        "lon": 80.2101,
        "workload": "moderate",
        "acclimatized": True,
        "work_start_hour": 7,
        "work_end_hour": 18,
        "language": "hi",
        "supervisor": {"name": "Supervisor", "telegram_chat_id": None},
        "backup": {"name": "Backup", "telegram_chat_id": None},
        "ack_timeout_seconds": 900,
    }
    base.update(overrides)
    return base


def rows(temp: float, rh: float, wind: float, ghi: float, direct: float) -> list[dict[str, Any]]:
    """24 identical-weather rows; radiation only between 06:00 and 18:00."""
    out = []
    for hour in range(24):
        daylight = 6 <= hour <= 18
        out.append(
            {
                "time": f"{DATE}T{hour:02d}:00",
                "air_temp_c": temp,
                "rh_pct": rh,
                "pressure_hpa": 1008.0,
                "wind_ms": wind,
                "ghi_wm2": ghi if daylight else 0.0,
                "direct_wm2": direct if daylight else 0.0,
            }
        )
    return out


HOT = dict(temp=36.0, rh=60, wind=2.0, ghi=850, direct=620)
COOL = dict(temp=22.0, rh=45, wind=3.0, ghi=400, direct=250)


def rows_from(per_hour: dict[int, dict[str, Any]], default: dict[str, Any]) -> list[dict[str, Any]]:
    """24 rows built from `default`, with specific hours overridden."""
    out = rows(**default)
    for hour, overrides in per_hour.items():
        out[hour].update(overrides)
    return out


# --- the six scenarios the card asks for -----------------------------------


def test_a_hot_day_is_dangerous_and_valid(capsys):
    plan = build_plan(site(), rows(**HOT), DATE, GENERATED_AT)
    assert validate_plan(plan) == []
    with capsys.disabled():
        print(
            f"\n  hot day: worst {plan['summary']['worst_level']}, "
            f"peak {plan['summary']['peak_wbgt_c']} C at {plan['summary']['peak_hour']}"
        )
    assert plan["summary"]["worst_level"] in ("RED", "STOP")
    assert plan["summary"]["windows"]


def test_a_cool_day_is_all_green_and_valid(capsys):
    plan = build_plan(site(), rows(**COOL), DATE, GENERATED_AT)
    assert validate_plan(plan) == []
    with capsys.disabled():
        print(f"  cool day: peak {plan['summary']['peak_wbgt_c']} C")
    assert plan["summary"]["worst_level"] == "GREEN"
    assert plan["summary"]["windows"] == []
    assert all(hour["level"] == "GREEN" for hour in plan["hours"])
    assert "within the screening limits all day" in plan["messages"]["en"]


def test_a_heavy_workload_day_is_capped_at_yellow_and_valid():
    plan = build_plan(site(workload="heavy"), rows(**COOL), DATE, GENERATED_AT)
    assert validate_plan(plan) == []
    # heavy work has no limit for band A, so even a cool day cannot be GREEN.
    assert plan["summary"]["worst_level"] == "YELLOW"
    work_hours = [hour for hour in plan["hours"] if hour["in_work_hours"]]
    assert all(hour["level"] == "YELLOW" for hour in work_hours)
    assert all("capped at YELLOW" in hour["reason"] for hour in work_hours)
    assert plan["summary"]["windows"]


def test_a_day_with_two_separate_windows(capsys):
    """Hot morning, cool midday, hot afternoon: two windows with a GREEN gap."""
    per_hour = {hour: dict(HOT) for hour in (7, 8, 9)}
    per_hour.update({hour: dict(HOT) for hour in (15, 16, 17)})
    built = rows(**COOL)
    for hour, overrides in per_hour.items():
        daylight = 6 <= hour <= 18
        built[hour].update(
            {
                "air_temp_c": overrides["temp"],
                "rh_pct": overrides["rh"],
                "wind_ms": overrides["wind"],
                "ghi_wm2": overrides["ghi"] if daylight else 0.0,
                "direct_wm2": overrides["direct"] if daylight else 0.0,
            }
        )
    plan = build_plan(site(), built, DATE, GENERATED_AT)
    assert validate_plan(plan) == []

    windows = plan["summary"]["windows"]
    with capsys.disabled():
        print(f"  two-window day: {[(w['start_hour'], w['end_hour'], w['level']) for w in windows]}")
    assert len(windows) >= 2
    # There is at least one GREEN work hour between the first and last window.
    gap = range(windows[0]["end_hour"], windows[-1]["start_hour"])
    assert any(
        plan["hours"][hour]["level"] == "GREEN" and plan["hours"][hour]["in_work_hours"]
        for hour in gap
    )


def test_two_missing_work_hours_become_unknown_and_are_skipped_by_windows():
    built = rows_from({10: {"rh_pct": None}, 11: {"rh_pct": None}}, HOT)
    plan = build_plan(site(), built, DATE, GENERATED_AT)
    assert validate_plan(plan) == []

    for hour in (10, 11):
        entry = plan["hours"][hour]
        assert entry["level"] == "UNKNOWN"
        assert entry["wbgt_c"] is None
        assert entry["max_work_min"] is None
        assert entry["min_rest_min"] is None
        assert entry["limit_c"] is None
        assert "missing" in entry["reason"].lower()

    for window in plan["summary"]["windows"]:
        assert 10 not in range(window["start_hour"], window["end_hour"])
        assert 11 not in range(window["start_hour"], window["end_hour"])

    # The rest of the day is still rated.
    assert plan["summary"]["worst_level"] in ("RED", "STOP")
    assert plan["summary"]["peak_hour"] not in (10, 11)


def test_a_day_with_every_work_hour_unknown():
    missing = {hour: {"air_temp_c": None} for hour in range(7, 18)}
    plan = build_plan(site(), rows_from(missing, HOT), DATE, GENERATED_AT)
    assert validate_plan(plan) == []

    summary = plan["summary"]
    assert summary["worst_level"] == "UNKNOWN"
    assert summary["peak_wbgt_c"] is None
    assert summary["peak_hour"] is None
    assert summary["windows"] == []
    assert "weather data was not available" in plan["messages"]["en"]


# --- shape and bookkeeping -------------------------------------------------


def test_plan_identity_and_profile():
    plan = build_plan(site(), rows(**HOT), DATE, GENERATED_AT)
    assert plan["plan_id"] == f"chn-01_{DATE}"
    assert plan["site_id"] == "chn-01"
    assert plan["date"] == DATE
    assert plan["generated_at"] == GENERATED_AT
    assert plan["profile"] == {"workload": "moderate", "acclimatized": True}
    assert plan["source"]["weather"] == "open-meteo"
    assert plan["source"]["thermofeel"] == "2.3.0"
    assert len(plan["hours"]) == 24


def test_work_hours_follow_the_site_window():
    plan = build_plan(site(work_start_hour=9, work_end_hour=12), rows(**HOT), DATE, GENERATED_AT)
    assert validate_plan(plan) == []
    inside = [hour["hour"] for hour in plan["hours"] if hour["in_work_hours"]]
    assert inside == [9, 10, 11]


def test_rounding_of_the_reported_inputs():
    built = rows_from(
        {12: {"air_temp_c": 36.149, "rh_pct": 59.6, "wind_ms": 2.049, "ghi_wm2": 849.7}}, HOT
    )
    hour = build_plan(site(), built, DATE, GENERATED_AT)["hours"][12]
    assert hour["air_temp_c"] == 36.1
    assert hour["rh_pct"] == 60
    assert hour["wind_ms"] == 2.0
    assert hour["ghi_wm2"] == 850


def test_missing_inputs_stay_null_in_the_hour_entry():
    built = rows_from({3: {"wind_ms": None, "ghi_wm2": None}}, HOT)
    hour = build_plan(site(), built, DATE, GENERATED_AT)["hours"][3]
    assert hour["wind_ms"] is None
    assert hour["ghi_wm2"] is None


def test_fallback_hours_are_counted_in_source():
    built = rows_from({h: {"wind_ms": None} for h in (8, 9, 10)}, HOT)
    plan = build_plan(site(), built, DATE, GENERATED_AT)
    assert validate_plan(plan) == []
    assert plan["source"]["simple_fallback_hours"] == 3


def test_source_omits_the_fallback_count_when_there_is_none():
    plan = build_plan(site(), rows(**HOT), DATE, GENERATED_AT)
    assert "simple_fallback_hours" not in plan["source"]
    assert plan["source"]["wbgt_method"] == "liljegren"


def test_weather_source_can_be_overridden_for_fixtures():
    plan = build_plan(site(), rows(**HOT), DATE, GENERATED_AT, weather_source="fixture")
    assert plan["source"]["weather"] == "fixture"
    assert validate_plan(plan) == []


def test_build_plan_rejects_a_day_that_is_not_24_hours():
    with pytest.raises(ValueError):
        build_plan(site(), rows(**HOT)[:12], DATE, GENERATED_AT)


# --- build_plan_for_site ---------------------------------------------------


def test_build_plan_for_site_uses_the_injected_fetch():
    def fake_fetch(lat, lon):
        hours = rows(**HOT)
        return {
            "hourly": {
                "time": [row["time"] for row in hours],
                "temperature_2m": [row["air_temp_c"] for row in hours],
                "relative_humidity_2m": [row["rh_pct"] for row in hours],
                "surface_pressure": [row["pressure_hpa"] for row in hours],
                "wind_speed_10m": [row["wind_ms"] for row in hours],
                "shortwave_radiation": [row["ghi_wm2"] for row in hours],
                "direct_radiation": [row["direct_wm2"] for row in hours],
            }
        }

    plan = build_plan_for_site(
        site(),
        now_utc=datetime(2026, 5, 14, 19, 0, tzinfo=timezone.utc),
        date_str=DATE,
        fetch=fake_fetch,
    )
    assert validate_plan(plan) == []
    assert plan["date"] == DATE
    assert plan["generated_at"] == "2026-05-14T19:00:00Z"


def test_india_today_rolls_over_before_utc_midnight():
    # 19:00 UTC is already 00:30 the next day in India.
    assert india_today(datetime(2026, 5, 14, 19, 0, tzinfo=timezone.utc)) == "2026-05-15"
    assert india_today(datetime(2026, 5, 14, 18, 0, tzinfo=timezone.utc)) == "2026-05-14"
