"""Solar zenith angle against known values (task P1.1 step 3)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shramshield_core.solar import cos_zenith

IST = timedelta(hours=5, minutes=30)

CHENNAI = (13.085, 80.2101)
DELHI = (28.6139, 77.209)

# (label, lat, lon, India-time datetime, expected cos zenith)
CASES = [
    ("Chennai 2024-05-15 12:05 IST", *CHENNAI, datetime(2024, 5, 15, 12, 5), 0.995),
    ("Chennai 2024-05-15 06:00 IST", *CHENNAI, datetime(2024, 5, 15, 6, 0), 0.053),
    ("Chennai 2024-05-15 15:00 IST", *CHENNAI, datetime(2024, 5, 15, 15, 0), 0.739),
    ("Chennai 2024-05-15 20:00 IST", *CHENNAI, datetime(2024, 5, 15, 20, 0), 0.0),
    ("Delhi 2024-06-21 12:20 IST", *DELHI, datetime(2024, 6, 21, 12, 20), 0.996),
    ("Delhi 2024-12-21 12:10 IST", *DELHI, datetime(2024, 12, 21, 12, 10), 0.614),
]


@pytest.mark.parametrize("label,lat,lon,when_ist,expected", CASES, ids=[c[0] for c in CASES])
def test_cos_zenith_known_values(label, lat, lon, when_ist, expected):
    got = cos_zenith(lat, lon, when_ist - IST)
    assert got == pytest.approx(expected, abs=0.01), f"{label}: got {got}"


def test_cos_zenith_is_zero_at_night():
    for hour in (0, 1, 2, 3, 22, 23):
        when_ist = datetime(2024, 5, 15, hour, 0)
        assert cos_zenith(*CHENNAI, when_ist - IST) == 0.0


def test_cos_zenith_stays_within_zero_and_one():
    for day in (1, 90, 180, 270, 365):
        for hour in range(24):
            when = datetime(2024, 1, 1) + timedelta(days=day - 1, hours=hour)
            assert 0.0 <= cos_zenith(*DELHI, when) <= 1.0


def test_summer_noon_is_higher_than_winter_noon_in_delhi():
    summer = cos_zenith(*DELHI, datetime(2024, 6, 21, 12, 0) - IST)
    winter = cos_zenith(*DELHI, datetime(2024, 12, 21, 12, 0) - IST)
    assert summer > winter
