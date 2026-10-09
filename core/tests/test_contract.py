"""Tests for the frozen contract constants and validators (task P1.0)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from shramshield_core.contract import (
    DISCLAIMER,
    LEVEL_FOR_BAND,
    LEVELS,
    LIMITS_C,
    MAX_WORK_MIN,
    validate_backtest,
    validate_plan,
    validate_run,
    validate_site,
)

FIXTURES = Path(__file__).resolve().parents[2] / "shared" / "fixtures"

# A literal second copy of the table in contract section 3.7. If this ever
# disagrees with LIMITS_C, one of the two was edited and the test must fail.
LIMITS_FROM_CONTRACT_3_7 = {
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


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def plan() -> dict:
    return load("plan_chennai_moderate.json")


@pytest.fixture
def demo_sites() -> list[dict]:
    return load("sites.json")["sites"]


# --- constants -------------------------------------------------------------


def test_limits_match_contract_section_3_7():
    assert LIMITS_C == LIMITS_FROM_CONTRACT_3_7


def test_levels_and_work_minutes():
    assert LEVELS == ["GREEN", "YELLOW", "ORANGE", "RED", "STOP"]
    assert LEVEL_FOR_BAND == {"A": "GREEN", "B": "YELLOW", "C": "ORANGE", "D": "RED"}
    assert MAX_WORK_MIN == {"GREEN": 60, "YELLOW": 45, "ORANGE": 30, "RED": 15, "STOP": 0}
    assert all(MAX_WORK_MIN[level] + (60 - MAX_WORK_MIN[level]) == 60 for level in LEVELS)


def test_disclaimer_is_the_contract_text():
    assert DISCLAIMER == (
        "Screening guidance estimated from weather-model data. It is not a measurement "
        "or medical advice. Use on-site judgement and stop work if anyone feels unwell."
    )


# --- every fixture validates ----------------------------------------------


def test_sites_fixture_validates(demo_sites):
    assert len(demo_sites) == 4
    for site in demo_sites:
        assert validate_site(site) == []


def test_plan_fixture_validates(plan):
    assert validate_plan(plan) == []


@pytest.mark.parametrize(
    "name",
    ["run_waiting.json", "run_escalated.json", "run_acknowledged.json", "run_unacknowledged.json"],
)
def test_run_fixtures_validate(name):
    assert validate_run(load(name)) == []


def test_backtest_fixture_validates():
    assert validate_backtest(load("backtest.json")) == []


# --- the validators actually reject bad input ------------------------------


def test_plan_with_a_wrong_level_fails(plan):
    broken = copy.deepcopy(plan)
    broken["hours"][0]["level"] = "STOP"
    errors = validate_plan(broken)
    assert errors
    assert any("level" in error for error in errors)


def test_plan_with_a_self_consistent_but_misclassified_hour_fails(plan):
    """Hour 0 is 25.0 C, which is GREEN for moderate acclimatized work.

    Relabel it RED and fix the minutes so only the WBGT-to-level rule is broken.
    """
    broken = copy.deepcopy(plan)
    hour = broken["hours"][0]
    hour["level"] = "RED"
    hour["max_work_min"] = 15
    hour["min_rest_min"] = 45
    hour["limit_c"] = 31.5
    errors = validate_plan(broken)
    assert any("classifies as GREEN" in error for error in errors), errors


def test_plan_with_a_wrong_disclaimer_fails(plan):
    broken = copy.deepcopy(plan)
    broken["disclaimer"] = "Totally safe, trust us."
    assert any("disclaimer" in error for error in validate_plan(broken))


def test_plan_with_a_missing_hour_fails(plan):
    broken = copy.deepcopy(plan)
    del broken["hours"][12]
    assert validate_plan(broken)


def test_site_rejects_latitude_outside_india(demo_sites):
    broken = copy.deepcopy(demo_sites[0])
    broken["lat"] = 40
    assert any("lat" in error for error in validate_site(broken))


def test_site_rejects_a_bad_site_id(demo_sites):
    for bad in ("CHN-01", "ab", "chn_01", "chennai-site-identifier-too-long"):
        broken = copy.deepcopy(demo_sites[0])
        broken["site_id"] = bad
        assert any("site_id" in error for error in validate_site(broken)), bad


def test_site_rejects_work_end_hour_not_after_start(demo_sites):
    broken = copy.deepcopy(demo_sites[0])
    broken["work_start_hour"] = 18
    broken["work_end_hour"] = 18
    assert any("work_end_hour" in error for error in validate_site(broken))


def test_site_rejects_an_unsupported_language(demo_sites):
    broken = copy.deepcopy(demo_sites[0])
    broken["language"] = "fr"
    assert any("language" in error for error in validate_site(broken))


def test_site_rejects_a_timeout_outside_the_range(demo_sites):
    for bad in (29, 3601):
        broken = copy.deepcopy(demo_sites[0])
        broken["ack_timeout_seconds"] = bad
        assert any("ack_timeout_seconds" in error for error in validate_site(broken)), bad


def test_run_rejects_an_active_stage_on_a_final_status():
    broken = load("run_acknowledged.json")
    broken["active_stage"] = "primary"
    assert any("active_stage" in error for error in validate_run(broken))


def test_run_rejects_an_unknown_event_step():
    broken = load("run_waiting.json")
    broken["events"][0]["step"] = "teleported"
    assert any("step" in error for error in validate_run(broken))


def test_backtest_rejects_counts_that_do_not_add_up():
    broken = load("backtest.json")
    broken["sites"][0]["by_threshold"][0]["missed"] += 1
    assert validate_backtest(broken)


def test_backtest_rejects_level_counts_that_do_not_sum():
    broken = load("backtest.json")
    broken["sites"][0]["level_counts"]["GREEN"] += 5
    assert any("level_counts" in error for error in validate_backtest(broken))
