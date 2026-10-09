"""Open-Meteo URL building, parsing and retries (task P1.1 step 4). No network."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from shramshield_core import weather
from shramshield_core.weather import (
    WeatherError,
    fetch_archive,
    fetch_forecast,
    parse_hourly,
    rows_for_date,
)

SAMPLE = Path(__file__).resolve().parent / "data" / "forecast_sample.json"


class FakeResponse(io.BytesIO):
    """Minimal stand-in for the object urlopen returns."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(payload, *, calls=None):
    def opener(request, timeout=None):
        if calls is not None:
            calls.append(request.full_url)
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    return opener


def minimal_response(hours=2):
    return {
        "hourly_units": {"temperature_2m": "°C"},
        "hourly": {
            "time": [f"2026-10-09T{hour:02d}:00" for hour in range(hours)],
            "temperature_2m": [30.0] * hours,
            "relative_humidity_2m": [60] * hours,
            "surface_pressure": [1008.0] * hours,
            "wind_speed_10m": [2.5] * hours,
            "shortwave_radiation": [0.0] * hours,
            "direct_radiation": [0.0] * hours,
        },
    }


# --- the saved real response ----------------------------------------------


def test_sample_response_is_a_real_trimmed_forecast():
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert "_note" in sample
    assert sample["timezone"] == "Asia/Kolkata"
    assert sample["utc_offset_seconds"] == 19800
    assert len(sample["hourly"]["time"]) == 6
    for name in weather.HOURLY_VARIABLES:
        assert name in sample["hourly"]


def test_parse_hourly_on_the_real_sample():
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    rows = parse_hourly(sample)
    assert len(rows) == 6
    assert set(rows[0]) == {
        "time",
        "air_temp_c",
        "rh_pct",
        "pressure_hpa",
        "wind_ms",
        "ghi_wm2",
        "direct_wm2",
    }
    assert rows[0]["time"].startswith("2026-")


# --- URL building ----------------------------------------------------------


def test_fetch_forecast_builds_the_contract_url():
    calls: list[str] = []
    fetch_forecast(13.085, 80.2101, urlopen=fake_urlopen(minimal_response(), calls=calls))
    url = calls[0]
    assert url.startswith(weather.FORECAST_URL)
    assert "past_days=1" in url
    assert "forecast_days=3" in url
    assert "wind_speed_unit=ms" in url
    assert "timezone=Asia%2FKolkata" in url
    for name in weather.HOURLY_VARIABLES:
        assert name in url


def test_fetch_archive_builds_the_contract_url():
    calls: list[str] = []
    fetch_archive(
        13.085,
        80.2101,
        "2024-04-01",
        "2024-06-30",
        urlopen=fake_urlopen(minimal_response(), calls=calls),
    )
    url = calls[0]
    assert url.startswith(weather.ARCHIVE_URL)
    assert "start_date=2024-04-01" in url
    assert "end_date=2024-06-30" in url
    assert "wind_speed_unit=ms" in url


# --- retries ---------------------------------------------------------------


def test_retries_a_server_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(weather, "PAUSE_SECONDS", 0)
    attempts = {"n": 0}

    def opener(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise urllib.error.HTTPError(request.full_url, 503, "busy", {}, None)
        return FakeResponse(json.dumps(minimal_response()).encode("utf-8"))

    response = fetch_forecast(13.0, 80.0, urlopen=opener)
    assert attempts["n"] == 3
    assert "hourly" in response


def test_gives_up_after_two_retries(monkeypatch):
    monkeypatch.setattr(weather, "PAUSE_SECONDS", 0)
    attempts = {"n": 0}

    def opener(request, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError(request.full_url, 500, "boom", {}, None)

    with pytest.raises(WeatherError):
        fetch_forecast(13.0, 80.0, urlopen=opener)
    assert attempts["n"] == 3


def test_does_not_retry_a_client_error(monkeypatch):
    monkeypatch.setattr(weather, "PAUSE_SECONDS", 0)
    attempts = {"n": 0}

    def opener(request, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError(request.full_url, 400, "bad", {}, None)

    with pytest.raises(WeatherError):
        fetch_forecast(13.0, 80.0, urlopen=opener)
    assert attempts["n"] == 1


def test_invalid_json_raises_weather_error():
    def opener(request, timeout=None):
        return FakeResponse(b"not json at all")

    with pytest.raises(WeatherError):
        fetch_forecast(13.0, 80.0, urlopen=opener)


# --- parsing errors --------------------------------------------------------


def test_parse_hourly_rejects_a_missing_variable():
    payload = minimal_response()
    del payload["hourly"]["wind_speed_10m"]
    with pytest.raises(WeatherError):
        parse_hourly(payload)


def test_parse_hourly_rejects_mismatched_list_lengths():
    payload = minimal_response()
    payload["hourly"]["temperature_2m"] = [30.0]
    with pytest.raises(WeatherError):
        parse_hourly(payload)


def test_parse_hourly_rejects_a_response_without_hourly():
    with pytest.raises(WeatherError):
        parse_hourly({"nope": 1})


def test_parse_hourly_keeps_nulls():
    payload = minimal_response()
    payload["hourly"]["relative_humidity_2m"] = [None, 55]
    rows = parse_hourly(payload)
    assert rows[0]["rh_pct"] is None
    assert rows[1]["rh_pct"] == 55


# --- rows_for_date ---------------------------------------------------------


def test_rows_for_date_returns_24_rows_in_order():
    payload = minimal_response(hours=48)
    payload["hourly"]["time"] = [f"2026-10-09T{hour:02d}:00" for hour in range(24)] + [
        f"2026-10-10T{hour:02d}:00" for hour in range(24)
    ]
    rows = rows_for_date(parse_hourly(payload), "2026-10-09")
    assert len(rows) == 24
    assert rows[0]["time"] == "2026-10-09T00:00"
    assert rows[-1]["time"] == "2026-10-09T23:00"


def test_rows_for_date_raises_when_the_date_is_not_covered():
    payload = minimal_response(hours=24)
    payload["hourly"]["time"] = [f"2026-10-09T{hour:02d}:00" for hour in range(24)]
    rows = parse_hourly(payload)
    with pytest.raises(WeatherError, match="date not covered"):
        rows_for_date(rows, "2026-10-11")


def test_rows_for_date_raises_on_a_partial_day():
    payload = minimal_response(hours=5)
    payload["hourly"]["time"] = [f"2026-10-09T{hour:02d}:00" for hour in range(5)]
    with pytest.raises(WeatherError, match="date not covered"):
        rows_for_date(parse_hourly(payload), "2026-10-09")
