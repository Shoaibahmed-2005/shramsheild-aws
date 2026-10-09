"""Supervisor messages in English and Hindi (contract section 3.8).

The templates are copied exactly from the contract. The Hindi wording still
needs review by a Hindi speaker (task P1.3).
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "en_hour",
    "hi_hour",
    "EN_LEVEL_NAMES",
    "HI_LEVEL_NAMES",
    "build_messages",
]

EN_LEVEL_NAMES: dict[str, str] = {
    "GREEN": "low",
    "YELLOW": "moderate",
    "ORANGE": "high",
    "RED": "very high",
    "STOP": "extreme",
}

HI_LEVEL_NAMES: dict[str, str] = {
    "GREEN": "कम",
    "YELLOW": "मध्यम",
    "ORANGE": "ज़्यादा",
    "RED": "बहुत ज़्यादा",
    "STOP": "अत्यधिक",
}

EN_WINDOW = (
    "{site}: today from {start} to {end} the heat-stress level is {level} "
    "(peak WBGT {peak:.1f} C at {peak_time}). "
    "In this window work at most {work} minutes per hour and rest at least "
    "{rest} minutes in shade. "
    "Drink about 240 mL of cool water every 20 minutes. Stop work and tell your "
    "supervisor if you feel dizzy, sick or confused."
)
EN_STOP = (
    "{site}: today from {start} to {end} heat stress is above the screening limits "
    "(peak WBGT {peak:.1f} C at {peak_time}). "
    "Stop non-essential work. Do only essential tasks, with a supervisor present, "
    "in shade, with frequent rests. "
    "Drink about 240 mL of cool water every 20 minutes."
)
EN_GREEN = (
    "{site}: heat stress is within the screening limits all day. Keep drinking water, "
    "about 240 mL every 20 minutes when working hard, and stop and tell your supervisor "
    "if you feel unwell."
)
EN_UNKNOWN = (
    "{site}: weather data was not available, so no heat plan could be made for today. "
    "Keep shade and water close, and stop work and tell your supervisor if you feel unwell."
)

HI_WINDOW = (
    "{site} साइट: आज {start} से {end} तक गर्मी का खतरा {level} रहेगा। "
    "सबसे ज़्यादा गर्मी {peak_time} के आसपास होगी। "
    "इस दौरान हर घंटे में ज़्यादा से ज़्यादा {work} मिनट काम करें और कम से कम "
    "{rest} मिनट छाया में आराम करें। "
    "हर 20 मिनट में लगभग एक गिलास ठंडा पानी पिएं। "
    "चक्कर, उल्टी या घबराहट हो तो तुरंत काम रोकें और सुपरवाइज़र को बताएं।"
)
HI_STOP = (
    "{site} साइट: आज {start} से {end} तक गर्मी का खतरा अत्यधिक रहेगा। "
    "इस समय ज़रूरी काम के अलावा बाकी सारा काम रोक दें। "
    "ज़रूरी काम भी सुपरवाइज़र की निगरानी में, छाया में और बार-बार आराम करके ही करें। "
    "हर 20 मिनट में लगभग एक गिलास ठंडा पानी पिएं।"
)
HI_GREEN = (
    "{site} साइट: आज दिन भर गर्मी का खतरा कम है। "
    "पानी पास रखें और भारी काम में हर 20 मिनट में पानी पिएं। "
    "तबीयत ठीक न लगे तो काम रोककर सुपरवाइज़र को बताएं।"
)
HI_UNKNOWN = (
    "{site} साइट: मौसम का डेटा अभी उपलब्ध नहीं है, इसलिए आज का गर्मी का अनुमान नहीं बन सका। "
    "छाया और पानी पास रखें, और तबीयत ठीक न लगे तो काम रोककर सुपरवाइज़र को बताएं।"
)

# Hindi time-of-day word by hour, per contract 3.8.
_HI_DAYPARTS: tuple[tuple[range, str], ...] = (
    (range(0, 4), "रात"),
    (range(4, 12), "सुबह"),
    (range(12, 16), "दोपहर"),
    (range(16, 19), "शाम"),
    (range(19, 24), "रात"),
)

_SEVERITY = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3, "STOP": 4}


def _twelve(hour: int) -> int:
    return hour % 12 or 12


def en_hour(hour: int) -> str:
    """12-hour clock text, for example 0 gives "12 AM" and 17 gives "5 PM"."""
    if not 0 <= hour <= 24:
        raise ValueError(f"hour out of range: {hour}")
    suffix = "AM" if hour % 24 < 12 else "PM"
    return f"{_twelve(hour % 24)} {suffix}"


def hi_hour(hour: int) -> str:
    """Hindi hour text, for example 9 gives "सुबह 9 बजे"."""
    if not 0 <= hour <= 24:
        raise ValueError(f"hour out of range: {hour}")
    normalised = hour % 24
    for span, word in _HI_DAYPARTS:
        if normalised in span:
            return f"{word} {_twelve(normalised)} बजे"
    raise ValueError(f"hour out of range: {hour}")  # pragma: no cover


def _worst_window(windows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Highest level, earliest window on a tie."""
    if not windows:
        return None
    return min(
        windows,
        key=lambda window: (-_SEVERITY[window["level"]], window["start_hour"]),
    )


def _peak_in_window(window: dict[str, Any], hours: list[dict[str, Any]]) -> tuple[float, int]:
    """Maximum WBGT inside the window, earliest hour on a tie."""
    inside = [
        hour
        for hour in hours
        if window["start_hour"] <= hour["hour"] < window["end_hour"]
        and hour.get("wbgt_c") is not None
    ]
    best = max(inside, key=lambda hour: (float(hour["wbgt_c"]), -int(hour["hour"])))
    return float(best["wbgt_c"]), int(best["hour"])


def build_messages(
    site: dict[str, Any],
    summary: dict[str, Any],
    hours: list[dict[str, Any]],
) -> dict[str, str]:
    """English and Hindi supervisor text for one plan."""
    name = site["name"]
    worst_level = summary.get("worst_level")

    if worst_level == "UNKNOWN":
        return {
            "en": EN_UNKNOWN.format(site=name),
            "hi": HI_UNKNOWN.format(site=name),
        }

    window = _worst_window(summary.get("windows") or [])
    if worst_level == "GREEN" or window is None:
        return {
            "en": EN_GREEN.format(site=name),
            "hi": HI_GREEN.format(site=name),
        }

    peak, peak_hour = _peak_in_window(window, hours)
    fields = {
        "site": name,
        "peak": peak,
        "work": window["max_work_min"],
        "rest": window["min_rest_min"],
    }
    en_fields = {
        **fields,
        "start": en_hour(window["start_hour"]),
        "end": en_hour(window["end_hour"]),
        "peak_time": en_hour(peak_hour),
        "level": EN_LEVEL_NAMES[window["level"]],
    }
    hi_fields = {
        **fields,
        "start": hi_hour(window["start_hour"]),
        "end": hi_hour(window["end_hour"]),
        "peak_time": hi_hour(peak_hour),
        "level": HI_LEVEL_NAMES[window["level"]],
    }

    if window["level"] == "STOP":
        return {"en": EN_STOP.format(**en_fields), "hi": HI_STOP.format(**hi_fields)}
    return {"en": EN_WINDOW.format(**en_fields), "hi": HI_WINDOW.format(**hi_fields)}
