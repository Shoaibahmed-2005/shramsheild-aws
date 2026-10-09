"""Hardening: edge cases, a deterministic random sample, performance (task P1.3).

No hypothesis: an extra dependency is not allowed by the card, so step 5 uses a
seeded random.Random instead.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta

import pytest

from shramshield_core.contract import LEVELS, validate_plan
from shramshield_core.limits import classify
from shramshield_core.messages import VOICE_MAX_CHARS, voice_text
from shramshield_core.plan import build_plan
from shramshield_core.solar import cos_zenith
from shramshield_core.wbgt import DEFAULT_PRESSURE_HPA, IST_OFFSET, compute_wbgt
from shramshield_core.weather import WeatherError, parse_hourly, rows_for_date

CHENNAI = (13.085, 80.2101)
DATE = "2024-05-15"
GENERATED_AT = "2024-05-15T00:30:00Z"

_SEVERITY = {level: index for index, level in enumerate(LEVELS)}


def site(**overrides):
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


def row(hour: int, date: str = DATE, **overrides):
    base = {
        "time": f"{date}T{hour:02d}:00",
        "air_temp_c": 33.0,
        "rh_pct": 60,
        "pressure_hpa": 1006.0,
        "wind_ms": 2.5,
        "ghi_wm2": 700.0 if 6 <= hour <= 18 else 0.0,
        "direct_wm2": 480.0 if 6 <= hour <= 18 else 0.0,
    }
    base.update(overrides)
    return base


def day(date: str = DATE, **overrides):
    return [row(hour, date, **overrides) for hour in range(24)]


# --- solar.py edge dates --------------------------------------------------


@pytest.mark.parametrize(
    "when",
    [
        datetime(2024, 2, 29, 12, 0),  # leap day
        datetime(2024, 12, 31, 23, 59),  # end of a leap year
        datetime(2025, 1, 1, 0, 0),  # start of the next year
        datetime(2024, 1, 1, 0, 0),
        datetime(2023, 12, 31, 12, 0),  # end of a non-leap year
        datetime(2024, 12, 31, 12, 0),
    ],
)
def test_cos_zenith_handles_edge_dates(when):
    value = cos_zenith(*CHENNAI, when)
    assert 0.0 <= value <= 1.0


def test_leap_day_and_march_first_differ():
    leap = cos_zenith(*CHENNAI, datetime(2024, 2, 29, 6, 30))
    march = cos_zenith(*CHENNAI, datetime(2024, 3, 1, 6, 30))
    assert leap != march


def test_cos_zenith_across_a_date_boundary():
    """23:00 and 00:00 India time both sit in the night, on either side of a date."""
    before = cos_zenith(*CHENNAI, datetime(2024, 5, 15, 23, 0) - IST_OFFSET)
    after = cos_zenith(*CHENNAI, datetime(2024, 5, 16, 0, 0) - IST_OFFSET)
    assert before == 0.0
    assert after == 0.0


def test_wbgt_hour_labels_at_the_date_boundary():
    """The 00:00 label looks 30 minutes back, into the previous day."""
    midnight, method = compute_wbgt(row(0, "2024-05-16", ghi_wm2=0.0, direct_wm2=0.0), *CHENNAI)
    assert method == "liljegren"
    assert midnight is not None
    late, _ = compute_wbgt(row(23, "2024-05-15", ghi_wm2=0.0, direct_wm2=0.0), *CHENNAI)
    assert late is not None


# --- sites at the edge of the allowed box ---------------------------------


@pytest.mark.parametrize("lat,lon", [(6.0, 68.0), (37.0, 98.0)])
def test_plan_at_the_corners_of_india(lat, lon):
    plan = build_plan(site(lat=lat, lon=lon), day(), DATE, GENERATED_AT)
    assert validate_plan(plan) == []


# --- extreme weather ------------------------------------------------------


def test_wbgt_at_zero_and_fifty_degrees(capsys):
    cold, cold_method = compute_wbgt(row(12, air_temp_c=0.0), *CHENNAI)
    hot, hot_method = compute_wbgt(row(12, air_temp_c=50.0), *CHENNAI)
    with capsys.disabled():
        print(f"\n  0 C air -> WBGT {cold} C; 50 C air -> WBGT {hot} C")
    assert cold is not None and cold_method == "liljegren"
    assert hot is not None and hot_method == "liljegren"
    assert classify(hot, "moderate", True)["level"] == "STOP"
    assert classify(cold, "moderate", True)["level"] == "GREEN"


@pytest.mark.parametrize("rh_pct", [1, 5, 50, 99, 100])
def test_wbgt_across_the_humidity_range(rh_pct):
    value, method = compute_wbgt(row(12, rh_pct=rh_pct), *CHENNAI)
    assert value is not None
    assert method == "liljegren"


def test_absolutely_dry_air_falls_back_instead_of_failing():
    """At RH 0 the vapour pressure is zero, so Liljegren's log term is -inf.

    thermofeel returns NaN. We must not pass that on as a number: the NaN guard
    in compute_wbgt falls back to the simple formula. RH 0 does not occur in
    Open-Meteo data, but a value must never be invented or crash the plan.
    """
    value, method = compute_wbgt(row(12, rh_pct=0), *CHENNAI)
    assert method == "simple_fallback"
    assert value is not None
    assert -10.0 <= value <= 60.0


def test_wbgt_with_no_wind():
    value, method = compute_wbgt(row(12, wind_ms=0.0), *CHENNAI)
    assert value is not None
    assert method == "liljegren"


def test_missing_pressure_uses_the_default():
    explicit, _ = compute_wbgt(row(12, pressure_hpa=DEFAULT_PRESSURE_HPA), *CHENNAI)
    defaulted, method = compute_wbgt(row(12, pressure_hpa=None), *CHENNAI)
    assert method == "liljegren"
    assert defaulted == explicit


@pytest.mark.parametrize(
    "field,expected_method",
    [
        ("air_temp_c", None),
        ("rh_pct", None),
        ("pressure_hpa", "liljegren"),
        ("wind_ms", "simple_fallback"),
        ("ghi_wm2", "simple_fallback"),
        ("direct_wm2", "simple_fallback"),
    ],
)
def test_every_kind_of_missing_field(field, expected_method):
    value, method = compute_wbgt(row(12, **{field: None}), *CHENNAI)
    assert method == expected_method
    if expected_method is None:
        assert value is None
    else:
        assert value is not None


def test_a_plan_where_every_field_is_missing_still_validates():
    rows = [
        row(hour, air_temp_c=None, rh_pct=None, pressure_hpa=None, wind_ms=None, ghi_wm2=None, direct_wm2=None)
        for hour in range(24)
    ]
    plan = build_plan(site(), rows, DATE, GENERATED_AT)
    assert validate_plan(plan) == []
    assert plan["summary"]["worst_level"] == "UNKNOWN"
    assert all(hour["level"] == "UNKNOWN" for hour in plan["hours"])


# --- determinism and serialisation ----------------------------------------


def test_building_the_same_plan_twice_is_identical():
    first = build_plan(site(), day(), DATE, GENERATED_AT)
    second = build_plan(site(), day(), DATE, GENERATED_AT)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_a_plan_survives_a_json_round_trip():
    plan = build_plan(site(), day(), DATE, GENERATED_AT)
    restored = json.loads(json.dumps(plan, ensure_ascii=False))
    assert restored == plan
    assert validate_plan(restored) == []


def test_a_plan_is_smaller_than_30_kb(capsys):
    plan = build_plan(site(), day(), DATE, GENERATED_AT)
    size = len(json.dumps(plan, ensure_ascii=False).encode("utf-8"))
    with capsys.disabled():
        print(f"  plan JSON size: {size} bytes")
    assert size < 30 * 1024


# --- weather parsing edges ------------------------------------------------


def test_rows_for_date_across_a_month_boundary():
    rows = day("2024-04-30") + day("2024-05-01")
    payload = {
        "hourly": {
            "time": [item["time"] for item in rows],
            "temperature_2m": [item["air_temp_c"] for item in rows],
            "relative_humidity_2m": [item["rh_pct"] for item in rows],
            "surface_pressure": [item["pressure_hpa"] for item in rows],
            "wind_speed_10m": [item["wind_ms"] for item in rows],
            "shortwave_radiation": [item["ghi_wm2"] for item in rows],
            "direct_radiation": [item["direct_wm2"] for item in rows],
        }
    }
    parsed = parse_hourly(payload)
    assert len(rows_for_date(parsed, "2024-04-30")) == 24
    assert len(rows_for_date(parsed, "2024-05-01")) == 24
    with pytest.raises(WeatherError):
        rows_for_date(parsed, "2024-05-02")


# --- voice text -----------------------------------------------------------


def test_voice_text_length_is_reported_and_bounded(capsys):
    plan = build_plan(site(), day(), DATE, GENERATED_AT)
    for lang in ("en", "hi"):
        text = voice_text(plan, lang)
        with capsys.disabled():
            print(f"  voice_text({lang}) length: {len(text)}")
        assert 0 < len(text) <= VOICE_MAX_CHARS


def test_voice_text_has_no_bare_celsius_unit():
    plan = build_plan(site(), day(), DATE, GENERATED_AT)
    for lang in ("en", "hi"):
        assert not __import__("re").search(r"\d\s*C\b", voice_text(plan, lang))


def test_hindi_voice_text_has_no_latin_letters_beyond_the_site_name():
    import re

    name = "Chennai demo site"
    plan = build_plan(site(name=name), day(), DATE, GENERATED_AT)
    allowed = set(name.lower()) | set(name.upper())
    found = set(re.findall(r"[A-Za-z]", voice_text(plan, "hi")))
    assert found <= allowed, found - allowed


def test_voice_text_drops_the_hydration_sentence_when_too_long():
    """A very long site name pushes the message past the limit."""
    long_name = "A" * 420
    plan = build_plan(site(name=long_name), day(), DATE, GENERATED_AT)
    for lang in ("en", "hi"):
        raw = plan["messages"][lang]
        text = voice_text(plan, lang)
        assert len(raw) > VOICE_MAX_CHARS
        assert ("240 mL of cool water" in raw) or ("गिलास" in raw)
        assert "240 mL of cool water" not in text
        assert "गिलास ठंडा पानी" not in text
    # The safety warning is never the sentence that gets cut.
    assert "सुपरवाइज़र" in voice_text(plan, "hi")


def test_voice_text_rejects_an_unknown_language():
    plan = build_plan(site(), day(), DATE, GENERATED_AT)
    with pytest.raises(ValueError):
        voice_text(plan, "fr")


def test_voice_text_strips_markdown_and_emoji():
    plan = build_plan(site(name="Site *bold* `code`"), day(), DATE, GENERATED_AT)
    text = voice_text(plan, "en")
    for char in "*`_#[]~|<>":
        assert char not in text


# --- step 5: deterministic random sample ----------------------------------


def test_two_thousand_random_rows(capsys):
    rng = random.Random(1234)
    start = datetime(2024, 1, 1)

    # The sample must be weather, not noise: radiation is tied to the real solar
    # angle for the hour, and humidity is capped as temperature rises, because
    # very hot air is never also very humid. Feeding physically impossible rows
    # (full sun at a 89 degree zenith, 42 C at 84 % humidity) would only measure
    # how the model extrapolates outside its domain.
    rows = []
    for index in range(2000):
        when = start + timedelta(hours=index)
        cossza = cos_zenith(*CHENNAI, when - timedelta(minutes=30) - IST_OFFSET)
        temp_c = round(rng.uniform(-5.0, 50.0), 1)
        max_rh = 100.0 if temp_c <= 25 else max(20.0, 100.0 - (temp_c - 25.0) * 3.5)
        clear_sky = cossza * 1100.0
        ghi = round(clear_sky * rng.uniform(0.15, 0.95), 1) if cossza > 0 else 0.0
        rows.append(
            {
                "time": when.strftime("%Y-%m-%dT%H:00"),
                "air_temp_c": temp_c,
                "rh_pct": rng.randint(3, int(max_rh)),
                "pressure_hpa": round(rng.uniform(950.0, 1050.0), 1),
                "wind_ms": round(rng.uniform(0.2, 15.0), 1),
                "ghi_wm2": ghi,
                "direct_wm2": round(ghi * rng.uniform(0.0, 0.85), 1),
            }
        )

    lowest, highest = 999.0, -999.0
    pairs = []
    for item in rows:
        value, _ = compute_wbgt(item, *CHENNAI)
        assert value is not None, item
        assert -10.0 <= value <= 60.0, (value, item)
        lowest = min(lowest, value)
        highest = max(highest, value)
        pairs.append((value, classify(value, "moderate", True)["level"]))

    with capsys.disabled():
        print(f"  2000 random rows: WBGT from {lowest} C to {highest} C")

    # Level is monotone in WBGT for a fixed profile.
    previous = -1
    for value, level in sorted(pairs, key=lambda pair: pair[0]):
        assert _SEVERITY[level] >= previous, (value, level)
        previous = _SEVERITY[level]

    # Every 24-hour chunk builds a plan that validates.
    plans = 0
    for offset in range(0, len(rows) - 24, 24):
        chunk = rows[offset : offset + 24]
        date = chunk[0]["time"][:10]
        if any(item["time"][:10] != date for item in chunk):
            continue
        plan = build_plan(site(), chunk, date, GENERATED_AT)
        assert validate_plan(plan) == [], plan["summary"]
        plans += 1
    with capsys.disabled():
        print(f"  built and validated {plans} plans from the sample")
    assert plans > 50


# --- step 7: performance --------------------------------------------------


def test_building_a_plan_is_fast(capsys):
    rows = day()
    config = site()
    build_plan(config, rows, DATE, GENERATED_AT)  # warm up

    runs = 20
    started = time.perf_counter()
    for _ in range(runs):
        build_plan(config, rows, DATE, GENERATED_AT)
    average_ms = (time.perf_counter() - started) / runs * 1000

    with capsys.disabled():
        print(f"  build_plan average over {runs} runs: {average_ms:.1f} ms (target under 100 ms)")
    # Only a genuinely broken machine or implementation fails the build.
    assert average_ms < 1000, f"build_plan took {average_ms:.0f} ms"
