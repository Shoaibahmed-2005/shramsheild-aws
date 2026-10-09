"""WBGT computation and the fallback rules (task P1.1 step 5).

Exact decimals are not asserted: the card asks for ranges plus one printed
line of the real values, so a thermofeel change shows up as a visible number
rather than a silently adjusted expectation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from shramshield_core.solar import cos_zenith
from shramshield_core.wbgt import IST_OFFSET, _solar_cos_for_row, compute_wbgt

CHENNAI = (13.085, 80.2101)

NOON = {
    "time": "2024-05-15T12:00",
    "air_temp_c": 36.0,
    "rh_pct": 55,
    "pressure_hpa": 1005,
    "wind_ms": 3.0,
    "ghi_wm2": 800,
    "direct_wm2": 560,
}
NIGHT = {**NOON, "time": "2024-05-15T23:00", "ghi_wm2": 0, "direct_wm2": 0}


def test_hot_humid_noon_is_in_a_sensible_range(capsys):
    wbgt_c, method = compute_wbgt(NOON, *CHENNAI)
    with capsys.disabled():
        print(f"\n  hot humid noon (36 C, 55 %, 3 m/s, 800 W/m2): {wbgt_c} C via {method}")
    assert method == "liljegren"
    assert 28 <= wbgt_c <= 36
    assert wbgt_c < NOON["air_temp_c"] + 2


def test_night_is_cooler_than_noon_for_the_same_air_temperature(capsys):
    noon_c, _ = compute_wbgt(NOON, *CHENNAI)
    night_c, method = compute_wbgt(NIGHT, *CHENNAI)
    with capsys.disabled():
        print(f"  same weather at night (no radiation): {night_c} C via {method}")
    assert night_c < noon_c


def test_missing_humidity_gives_no_value_and_no_method():
    assert compute_wbgt({**NOON, "rh_pct": None}, *CHENNAI) == (None, None)


def test_missing_temperature_gives_no_value_and_no_method():
    assert compute_wbgt({**NOON, "air_temp_c": None}, *CHENNAI) == (None, None)


def test_missing_wind_falls_back_to_the_simple_formula():
    wbgt_c, method = compute_wbgt({**NOON, "wind_ms": None}, *CHENNAI)
    assert method == "simple_fallback"
    assert wbgt_c is not None


def test_missing_radiation_falls_back_to_the_simple_formula():
    _, method = compute_wbgt({**NOON, "ghi_wm2": None}, *CHENNAI)
    assert method == "simple_fallback"
    _, method = compute_wbgt({**NOON, "direct_wm2": None}, *CHENNAI)
    assert method == "simple_fallback"


def test_missing_pressure_still_uses_liljegren():
    with_pressure, _ = compute_wbgt(NOON, *CHENNAI)
    without, method = compute_wbgt({**NOON, "pressure_hpa": None}, *CHENNAI)
    assert method == "liljegren"
    assert abs(without - with_pressure) < 1.0


def test_the_fallback_overestimates_at_night(capsys):
    liljegren_c, _ = compute_wbgt(NIGHT, *CHENNAI)
    fallback_c, method = compute_wbgt({**NIGHT, "wind_ms": None}, *CHENNAI)
    with capsys.disabled():
        print(f"  night: liljegren {liljegren_c} C vs simple fallback {fallback_c} C")
    assert method == "simple_fallback"
    assert fallback_c >= liljegren_c


def test_solar_angle_uses_the_half_hour_before_the_label():
    """Open-Meteo radiation is the mean of the preceding hour (contract 3.6)."""
    row = {"time": "2024-05-15T12:00"}
    got = _solar_cos_for_row(row, *CHENNAI)
    expected = cos_zenith(*CHENNAI, datetime(2024, 5, 15, 11, 30) - IST_OFFSET)
    assert got == expected

    naive_label = cos_zenith(*CHENNAI, datetime(2024, 5, 15, 12, 0) - IST_OFFSET)
    assert got != naive_label


def test_values_are_rounded_to_one_decimal():
    wbgt_c, _ = compute_wbgt(NOON, *CHENNAI)
    assert round(wbgt_c, 1) == wbgt_c


def test_a_calm_sunny_hour_can_exceed_air_temperature(capsys):
    """Low wind means little convective cooling, so the globe term dominates.

    This is a real property of the Liljegren method, not a bug: it is why the
    plan for a near-calm humid morning can read above the air temperature.
    """
    calm = {**NOON, "wind_ms": 0.5, "air_temp_c": 30.0, "rh_pct": 70, "ghi_wm2": 400, "direct_wm2": 250}
    wbgt_c, method = compute_wbgt(calm, *CHENNAI)
    with capsys.disabled():
        print(f"  near-calm sunny hour (30 C, 70 %, 0.5 m/s, 400 W/m2): {wbgt_c} C via {method}")
    assert method == "liljegren"
    assert wbgt_c > calm["air_temp_c"]


def test_night_hours_get_no_radiation_term():
    """When the sun is down, ssrd and fdir are forced to zero (contract 3.6)."""
    bogus_night = {**NIGHT, "ghi_wm2": 900, "direct_wm2": 700}
    forced_zero, _ = compute_wbgt(bogus_night, *CHENNAI)
    actual_night, _ = compute_wbgt(NIGHT, *CHENNAI)
    assert forced_zero == actual_night


def test_india_time_rows_are_converted_before_the_solar_call():
    """A 06:00 IST label maps to 00:30 UTC for the mid-hour solar angle."""
    row = {"time": "2024-05-15T06:00"}
    got = _solar_cos_for_row(row, *CHENNAI)
    expected = cos_zenith(*CHENNAI, datetime(2024, 5, 15, 5, 30) - timedelta(hours=5, minutes=30))
    assert got == expected
