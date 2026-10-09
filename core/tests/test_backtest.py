"""Backtest counting rules (task P1.2 step 7).

The synthetic case uses three hand-written days so the expected counts can be
worked out on paper, independently of thermofeel.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shramshield_core.backtest import (
    DANGEROUS_LEVELS,
    DEFAULT_THRESHOLDS_C,
    REQUIRED_CAVEATS,
    backtest_site,
    combine_totals,
    threshold_row,
)
from shramshield_core.contract import LEVELS, validate_backtest

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_BACKTEST = REPO_ROOT / "core" / "data" / "backtest" / "backtest.json"
SHARED_BACKTEST = REPO_ROOT / "shared" / "fixtures" / "backtest.json"

SITE = {
    "site_id": "tst-01",
    "name": "Test site",
    "lat": 13.085,
    "lon": 80.2101,
}

PROFILE = {
    "workload": "moderate",
    "acclimatized": True,
    "work_start_hour": 7,
    "work_end_hour": 18,
}


def synthetic_rows() -> list[dict]:
    """Three days x 24 hours.

    Day 1 is hot and humid with almost no wind: 31 C air, WBGT about 34 C.
    Day 2 is far hotter but bone dry and windy: 41 C air, WBGT about 28 C.
    Day 3 is mild.

    So a thermometer fires on day 2 and stays silent on day 1, while the heat
    stress is the other way round. That is the whole point of the project.
    """
    days = [
        ("2024-05-01", 31.0, 80, 1.0, 800, 560),
        ("2024-05-02", 41.0, 12, 9.0, 950, 750),
        ("2024-05-03", 24.0, 50, 3.0, 400, 250),
    ]
    rows = []
    for date, temp, rh, wind, ghi, direct in days:
        for hour in range(24):
            daylight = 7 <= hour < 18
            rows.append(
                {
                    "time": f"{date}T{hour:02d}:00",
                    "air_temp_c": temp if daylight else temp - 6,
                    "rh_pct": rh,
                    "pressure_hpa": 1006.0,
                    "wind_ms": wind,
                    "ghi_wm2": ghi if daylight else 0.0,
                    "direct_wm2": direct if daylight else 0.0,
                }
            )
    return rows


@pytest.fixture(scope="module")
def synthetic_result() -> dict:
    return backtest_site(SITE, synthetic_rows(), **PROFILE)


# --- the synthetic case ----------------------------------------------------


def test_only_work_hours_are_counted(synthetic_result):
    # 3 days x 11 work hours (07:00 up to but not including 18:00)
    assert synthetic_result["work_hours_total"] == 33
    assert synthetic_result["work_hours_with_data"] == 33


def test_level_counts_sum_to_hours_with_data(synthetic_result):
    assert sum(synthetic_result["level_counts"].values()) == 33
    assert set(synthetic_result["level_counts"]) == set(LEVELS)


def test_dangerous_hours_match_the_level_counts(synthetic_result):
    counts = synthetic_result["level_counts"]
    assert synthetic_result["dangerous_hours"] == counts["RED"] + counts["STOP"]


def test_the_humid_day_is_dangerous_and_the_dry_day_is_not(capsys):
    """The point of the project: 31 C humid and calm beats 41 C dry and windy."""
    rows = synthetic_rows()
    humid = backtest_site(SITE, rows[0:24], **PROFILE)
    dry = backtest_site(SITE, rows[24:48], **PROFILE)
    mild = backtest_site(SITE, rows[48:72], **PROFILE)
    with capsys.disabled():
        print(
            f"\n  humid 31 C day: {humid['dangerous_hours']} dangerous of 11; "
            f"dry 41 C day: {dry['dangerous_hours']}; mild 24 C day: {mild['dangerous_hours']}"
        )
    assert humid["dangerous_hours"] == 11, "every work hour of the humid day is dangerous"
    assert dry["dangerous_hours"] < humid["dangerous_hours"], (
        "the 41 C dry day must be less dangerous than the 31 C humid day"
    )
    assert mild["dangerous_hours"] == 0

    # A 40 C thermometer is silent all through the dangerous humid day...
    humid_40 = next(row for row in humid["by_threshold"] if row["threshold_c"] == 40)
    assert humid_40["alert_hours"] == 0
    assert humid_40["missed"] == 11

    # ...and fires on every hour of the dry day, mostly on hours that are not.
    dry_40 = next(row for row in dry["by_threshold"] if row["threshold_c"] == 40)
    assert dry_40["alert_hours"] == 11
    assert dry_40["false_alarm_hours"] > dry["dangerous_hours"]


def test_a_40c_baseline_misses_the_humid_day(synthetic_result):
    """Only the 41 C dry day trips a 40 C thermometer."""
    at_40 = next(
        row for row in synthetic_result["by_threshold"] if row["threshold_c"] == 40
    )
    # Day 2 is the only day at or above 40 C, so exactly its 11 work hours alert.
    assert at_40["alert_hours"] == 11
    assert at_40["caught"] + at_40["missed"] == synthetic_result["dangerous_hours"]
    assert at_40["missed"] > 0


def test_caught_plus_missed_equals_dangerous_at_every_threshold(synthetic_result):
    for row in synthetic_result["by_threshold"]:
        assert row["caught"] + row["missed"] == synthetic_result["dangerous_hours"]


def test_missed_pct_follows_the_counts(synthetic_result):
    dangerous = synthetic_result["dangerous_hours"]
    for row in synthetic_result["by_threshold"]:
        expected = round(100.0 * row["missed"] / dangerous, 1)
        assert row["missed_pct"] == expected


def test_thresholds_are_the_contract_defaults(synthetic_result):
    assert [row["threshold_c"] for row in synthetic_result["by_threshold"]] == list(
        DEFAULT_THRESHOLDS_C
    )


def test_a_higher_threshold_never_catches_more(synthetic_result):
    caught = [row["caught"] for row in synthetic_result["by_threshold"]]
    assert caught == sorted(caught, reverse=True)


def test_example_hour_is_the_coolest_dangerous_hour(synthetic_result):
    example = synthetic_result["example_hour"]
    assert example is not None
    assert example["level"] in DANGEROUS_LEVELS
    # The humid day sits at 31.0 C in work hours, cooler than the dry 41 C day.
    assert example["air_temp_c"] == 31.0


def test_example_hour_is_none_when_nothing_is_dangerous():
    mild = synthetic_rows()[48:72]
    result = backtest_site(SITE, mild, **PROFILE)
    assert result["dangerous_hours"] == 0
    assert result["example_hour"] is None
    assert all(row["missed_pct"] == 0.0 for row in result["by_threshold"])


def test_false_alarms_count_green_and_yellow_alert_hours():
    """The 41 C dry day alerts at 40 C; hours rated GREEN or YELLOW are false alarms."""
    dry = backtest_site(SITE, synthetic_rows()[24:48], **PROFILE)
    at_40 = next(row for row in dry["by_threshold"] if row["threshold_c"] == 40)
    counts = dry["level_counts"]
    assert at_40["false_alarm_hours"] == counts["GREEN"] + counts["YELLOW"]


def test_threshold_row_on_hand_built_hours():
    hours = [
        {"air_temp_c": 41.0, "level": "STOP"},
        {"air_temp_c": 41.0, "level": "GREEN"},
        {"air_temp_c": 30.0, "level": "RED"},
        {"air_temp_c": 30.0, "level": "GREEN"},
        {"air_temp_c": None, "level": "RED"},
    ]
    row = threshold_row(40, hours, dangerous_hours=3)
    assert row["alert_hours"] == 2
    assert row["caught"] == 1
    assert row["missed"] == 2
    assert row["missed_pct"] == pytest.approx(66.7)
    assert row["false_alarm_hours"] == 1


def test_hours_with_no_air_temperature_never_alert():
    hours = [{"air_temp_c": None, "level": "STOP"}]
    row = threshold_row(40, hours, dangerous_hours=1)
    assert row["alert_hours"] == 0
    assert row["caught"] == 0
    assert row["missed"] == 1


def test_missing_humidity_makes_an_hour_unknown_and_uncounted():
    rows = synthetic_rows()[0:24]
    for hour in range(7, 10):
        rows[hour]["rh_pct"] = None
    result = backtest_site(SITE, rows, **PROFILE)
    assert result["work_hours_total"] == 11
    assert result["work_hours_with_data"] == 8
    assert sum(result["level_counts"].values()) == 8


# --- totals ---------------------------------------------------------------


def test_totals_are_the_sum_of_the_sites(synthetic_result):
    sites = [synthetic_result, synthetic_result]
    totals = combine_totals(sites)
    assert totals["dangerous_hours"] == 2 * synthetic_result["dangerous_hours"]
    for index, row in enumerate(totals["by_threshold"]):
        per_site = synthetic_result["by_threshold"][index]
        assert row["caught"] == 2 * per_site["caught"]
        assert row["missed"] == 2 * per_site["missed"]
        assert row["alert_hours"] == 2 * per_site["alert_hours"]
        assert row["false_alarm_hours"] == 2 * per_site["false_alarm_hours"]
        assert row["caught"] + row["missed"] == totals["dangerous_hours"]


def test_totals_of_no_sites_are_zero():
    totals = combine_totals([])
    assert totals["dangerous_hours"] == 0
    assert all(row["missed_pct"] == 0.0 for row in totals["by_threshold"])


# --- the real output ------------------------------------------------------


@pytest.fixture(scope="module")
def real_backtest() -> dict:
    if not REAL_BACKTEST.exists():
        pytest.skip("run scripts/run_backtest.py first")
    return json.loads(REAL_BACKTEST.read_text(encoding="utf-8"))


def test_the_real_backtest_is_valid(real_backtest):
    assert validate_backtest(real_backtest) == []


def test_the_real_backtest_is_not_a_fixture(real_backtest):
    assert real_backtest["_fixture"] is False
    assert real_backtest["sources"]["weather"] == "Open-Meteo archive (ERA5 based reanalysis)"


def test_the_real_totals_equal_the_sum_of_the_sites(real_backtest):
    sites = real_backtest["sites"]
    totals = real_backtest["totals"]
    assert totals["dangerous_hours"] == sum(site["dangerous_hours"] for site in sites)
    for index, row in enumerate(totals["by_threshold"]):
        entries = [site["by_threshold"][index] for site in sites]
        assert row["caught"] == sum(entry["caught"] for entry in entries)
        assert row["missed"] == sum(entry["missed"] for entry in entries)
        assert row["alert_hours"] == sum(entry["alert_hours"] for entry in entries)
        assert row["false_alarm_hours"] == sum(entry["false_alarm_hours"] for entry in entries)


def test_the_real_backtest_covers_the_four_demo_sites(real_backtest):
    assert [site["site_id"] for site in real_backtest["sites"]] == [
        "chn-01",
        "del-01",
        "kol-01",
        "hyd-01",
    ]
    for site in real_backtest["sites"]:
        # 91 days x 11 work hours
        assert site["work_hours_total"] == 1001


def test_the_real_backtest_carries_every_required_caveat(real_backtest):
    for caveat in REQUIRED_CAVEATS:
        assert caveat in real_backtest["caveats"]


def test_the_shared_fixture_copy_matches_the_core_output(real_backtest):
    shared = json.loads(SHARED_BACKTEST.read_text(encoding="utf-8"))
    assert shared == real_backtest
