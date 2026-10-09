"""ACGIH band classification at the boundaries (task P1.1 step 6)."""

from __future__ import annotations

import pytest

from shramshield_core.contract import LEVELS, LIMITS_C, MAX_WORK_MIN
from shramshield_core.limits import classify

_SEVERITY = {level: index for index, level in enumerate(LEVELS)}

# (wbgt_c, workload, acclimatized, expected level) straight from the card
BOUNDARIES = [
    (28.0, "moderate", True, "GREEN"),
    (28.1, "moderate", True, "YELLOW"),
    (29.0, "moderate", True, "YELLOW"),
    (29.1, "moderate", True, "ORANGE"),
    (30.0, "moderate", True, "ORANGE"),
    (30.1, "moderate", True, "RED"),
    (31.5, "moderate", True, "RED"),
    (31.6, "moderate", True, "STOP"),
    (15.0, "heavy", True, "YELLOW"),
    (15.0, "very_heavy", True, "ORANGE"),
    (28.0, "light", False, "GREEN"),
    (28.1, "light", False, "YELLOW"),
    (27.0, "very_heavy", False, "RED"),
    (27.1, "very_heavy", False, "STOP"),
]


@pytest.mark.parametrize("wbgt_c,workload,acclimatized,expected", BOUNDARIES)
def test_boundaries(wbgt_c, workload, acclimatized, expected):
    assert classify(wbgt_c, workload, acclimatized)["level"] == expected


@pytest.mark.parametrize("wbgt_c,workload,acclimatized,expected", BOUNDARIES)
def test_minutes_follow_the_level(wbgt_c, workload, acclimatized, expected):
    band = classify(wbgt_c, workload, acclimatized)
    assert band["max_work_min"] == MAX_WORK_MIN[expected]
    assert band["min_rest_min"] == 60 - MAX_WORK_MIN[expected]
    assert band["max_work_min"] + band["min_rest_min"] == 60


def test_level_never_decreases_as_wbgt_rises():
    for state in ("acclimatized", "unacclimatized"):
        acclimatized = state == "acclimatized"
        for workload in LIMITS_C[state]:
            previous = -1
            for step in range(0, 301):
                wbgt_c = round(10.0 + step * 0.1, 1)
                level = classify(wbgt_c, workload, acclimatized)["level"]
                severity = _SEVERITY[level]
                assert severity >= previous, (
                    f"{workload} {state}: level dropped to {level} at {wbgt_c} C"
                )
                previous = severity


def test_heavy_work_is_capped_at_yellow_with_an_explanation():
    band = classify(15.0, "heavy", True)
    assert band["level"] == "YELLOW"
    assert "capped at YELLOW" in band["reason"]


def test_very_heavy_work_is_capped_at_orange_with_an_explanation():
    band = classify(15.0, "very_heavy", True)
    assert band["level"] == "ORANGE"
    assert "capped at ORANGE" in band["reason"]


def test_moderate_work_is_not_capped():
    assert "capped" not in classify(15.0, "moderate", True)["reason"]


def test_matched_band_reason_text():
    assert classify(29.5, "moderate", True)["reason"] == (
        "WBGT 29.5 C is within the 30.0 C limit for 25-50% work "
        "(moderate work, acclimatized)."
    )


def test_stop_reason_text():
    assert classify(32.0, "moderate", True)["reason"] == (
        "WBGT 32.0 C is above every screening limit for moderate work "
        "(acclimatized); highest limit is 31.5 C."
    )


def test_limit_c_is_the_matched_band_limit():
    assert classify(29.5, "moderate", True)["limit_c"] == 30.0
    assert classify(28.0, "moderate", True)["limit_c"] == 28.0
    assert classify(32.0, "moderate", True)["limit_c"] is None


def test_unknown_when_wbgt_is_missing():
    band = classify(None, "moderate", True)
    assert band["level"] == "UNKNOWN"
    assert band["max_work_min"] is None
    assert band["min_rest_min"] is None
    assert band["limit_c"] is None
    assert band["reason"] == (
        "Temperature or humidity data missing for this hour; no advice given."
    )


def test_unknown_workload_is_rejected():
    with pytest.raises(ValueError):
        classify(30.0, "extreme", True)


def test_unacclimatized_is_never_more_permissive_than_acclimatized():
    for workload in ("light", "moderate", "heavy", "very_heavy"):
        for step in range(0, 301):
            wbgt_c = round(10.0 + step * 0.1, 1)
            acc = classify(wbgt_c, workload, True)["level"]
            unacc = classify(wbgt_c, workload, False)["level"]
            assert _SEVERITY[unacc] >= _SEVERITY[acc], (workload, wbgt_c)
