"""Hour texts and message templates (task P1.1 step 7)."""

from __future__ import annotations

import pytest

from shramshield_core.messages import (
    EN_LEVEL_NAMES,
    HI_LEVEL_NAMES,
    build_messages,
    en_hour,
    hi_hour,
)

SITE = {"name": "Chennai demo site"}

HI_HOURS = {
    9: "सुबह 9 बजे",
    12: "दोपहर 12 बजे",
    17: "शाम 5 बजे",
    0: "रात 12 बजे",
    21: "रात 9 बजे",
    4: "सुबह 4 बजे",
    13: "दोपहर 1 बजे",
}

EN_HOURS = {0: "12 AM", 12: "12 PM", 17: "5 PM"}


@pytest.mark.parametrize("hour,expected", sorted(HI_HOURS.items()))
def test_hi_hour(hour, expected):
    assert hi_hour(hour) == expected


@pytest.mark.parametrize("hour,expected", sorted(EN_HOURS.items()))
def test_en_hour(hour, expected):
    assert en_hour(hour) == expected


def test_every_hour_has_text_in_both_languages():
    for hour in range(24):
        assert en_hour(hour)
        assert hi_hour(hour).endswith("बजे")


def test_level_names_cover_every_level():
    assert set(EN_LEVEL_NAMES) == set(HI_LEVEL_NAMES)
    assert EN_LEVEL_NAMES["ORANGE"] == "high"
    assert HI_LEVEL_NAMES["STOP"] == "अत्यधिक"


def hours_with(levels: dict[int, tuple[str, float]]) -> list[dict]:
    """24 hour entries; levels maps hour -> (level, wbgt_c)."""
    out = []
    for hour in range(24):
        level, wbgt = levels.get(hour, ("GREEN", 24.0))
        out.append(
            {
                "hour": hour,
                "in_work_hours": 7 <= hour < 18,
                "wbgt_c": wbgt,
                "level": level,
            }
        )
    return out


def no_leftover_braces(messages: dict[str, str]) -> None:
    for text in messages.values():
        assert "{" not in text and "}" not in text
        assert text.strip()


def test_a_green_day_uses_the_green_template():
    summary = {"worst_level": "GREEN", "peak_wbgt_c": 24.0, "peak_hour": 13, "windows": []}
    messages = build_messages(SITE, summary, hours_with({}))
    no_leftover_braces(messages)
    assert "within the screening limits all day" in messages["en"]
    assert "गर्मी का खतरा कम है" in messages["hi"]


def test_a_stop_day_uses_the_stop_template():
    summary = {
        "worst_level": "STOP",
        "peak_wbgt_c": 32.0,
        "peak_hour": 14,
        "windows": [
            {"start_hour": 14, "end_hour": 15, "level": "STOP", "max_work_min": 0, "min_rest_min": 60}
        ],
    }
    messages = build_messages(SITE, summary, hours_with({14: ("STOP", 32.0)}))
    no_leftover_braces(messages)
    assert "above the screening limits" in messages["en"]
    assert "peak WBGT 32.0 C at 2 PM" in messages["en"]
    assert "from 2 PM to 3 PM" in messages["en"]
    assert "दोपहर 2 बजे से दोपहर 3 बजे" in messages["hi"]
    assert "अत्यधिक" in messages["hi"]


def test_a_window_day_uses_the_window_template():
    summary = {
        "worst_level": "ORANGE",
        "peak_wbgt_c": 29.8,
        "peak_hour": 13,
        "windows": [
            {
                "start_hour": 12,
                "end_hour": 15,
                "level": "ORANGE",
                "max_work_min": 30,
                "min_rest_min": 30,
            }
        ],
    }
    hours = hours_with({12: ("ORANGE", 29.5), 13: ("ORANGE", 29.8), 14: ("ORANGE", 29.2)})
    messages = build_messages(SITE, summary, hours)
    no_leftover_braces(messages)
    assert "the heat-stress level is high" in messages["en"]
    assert "peak WBGT 29.8 C at 1 PM" in messages["en"]
    assert "work at most 30 minutes per hour" in messages["en"]
    assert "rest at least 30 minutes" in messages["en"]
    assert "ज़्यादा" in messages["hi"]
    assert "30 मिनट" in messages["hi"]


def test_an_unknown_day_uses_the_unknown_template():
    summary = {"worst_level": "UNKNOWN", "peak_wbgt_c": None, "peak_hour": None, "windows": []}
    messages = build_messages(SITE, summary, hours_with({}))
    no_leftover_braces(messages)
    assert "weather data was not available" in messages["en"]
    assert "मौसम का डेटा अभी उपलब्ध नहीं है" in messages["hi"]


def test_the_worst_window_is_the_highest_level_then_the_earliest():
    summary = {
        "worst_level": "RED",
        "peak_wbgt_c": 31.0,
        "peak_hour": 16,
        "windows": [
            {"start_hour": 8, "end_hour": 9, "level": "YELLOW", "max_work_min": 45, "min_rest_min": 15},
            {"start_hour": 10, "end_hour": 11, "level": "RED", "max_work_min": 15, "min_rest_min": 45},
            {"start_hour": 16, "end_hour": 17, "level": "RED", "max_work_min": 15, "min_rest_min": 45},
        ],
    }
    hours = hours_with({8: ("YELLOW", 28.5), 10: ("RED", 30.8), 16: ("RED", 31.0)})
    messages = build_messages(SITE, summary, hours)
    # The 10:00 RED window wins: highest level, earliest of the two.
    assert "from 10 AM to 11 AM" in messages["en"]
    assert "peak WBGT 30.8 C at 10 AM" in messages["en"]


def test_the_peak_quoted_is_the_peak_inside_the_worst_window():
    summary = {
        "worst_level": "ORANGE",
        "peak_wbgt_c": 29.9,
        "peak_hour": 9,
        "windows": [
            {
                "start_hour": 12,
                "end_hour": 14,
                "level": "ORANGE",
                "max_work_min": 30,
                "min_rest_min": 30,
            }
        ],
    }
    # Hour 9 is hotter overall but sits outside the window, so it is not quoted.
    hours = hours_with({9: ("GREEN", 29.9), 12: ("ORANGE", 29.1), 13: ("ORANGE", 29.4)})
    messages = build_messages(SITE, summary, hours)
    assert "peak WBGT 29.4 C at 1 PM" in messages["en"]
