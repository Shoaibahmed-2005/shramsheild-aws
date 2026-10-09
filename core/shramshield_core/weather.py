"""Open-Meteo access and row parsing (contract section 3.12).

Standard library only. Every network call goes through an injectable
``urlopen`` so tests never touch the network.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

__all__ = [
    "WeatherError",
    "HOURLY_VARIABLES",
    "FORECAST_URL",
    "ARCHIVE_URL",
    "fetch_forecast",
    "fetch_archive",
    "parse_hourly",
    "rows_for_date",
]

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARIABLES: tuple[str, ...] = (
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_10m",
    "shortwave_radiation",
    "direct_radiation",
)

# Open-Meteo variable name -> row key used everywhere else in the package.
_ROW_KEYS: dict[str, str] = {
    "temperature_2m": "air_temp_c",
    "relative_humidity_2m": "rh_pct",
    "surface_pressure": "pressure_hpa",
    "wind_speed_10m": "wind_ms",
    "shortwave_radiation": "ghi_wm2",
    "direct_radiation": "direct_wm2",
}

USER_AGENT = "shramshield/0.1 (hackathon)"
TIMEOUT_SECONDS = 15
MAX_RETRIES = 2
PAUSE_SECONDS = 1.0


class WeatherError(Exception):
    """Open-Meteo could not be read, or answered something unusable."""


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return isinstance(exc, (urllib.error.URLError, TimeoutError, OSError))


def _get_json(url: str, urlopen: Callable[..., Any] | None) -> dict[str, Any]:
    """GET a JSON document, retrying transient failures up to MAX_RETRIES times."""
    opener = urlopen or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    last: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with opener(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read()
            break
        except Exception as exc:  # noqa: BLE001 - re-raised as WeatherError below
            last = exc
            if not _should_retry(exc) or attempt == MAX_RETRIES:
                raise WeatherError(f"Open-Meteo request failed: {exc}") from exc
            time.sleep(PAUSE_SECONDS)
    else:  # pragma: no cover - the loop always breaks or raises
        raise WeatherError(f"Open-Meteo request failed: {last}")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WeatherError(f"Open-Meteo returned invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise WeatherError("Open-Meteo returned JSON that is not an object")
    if "error" in payload and payload.get("error"):
        raise WeatherError(f"Open-Meteo reported an error: {payload.get('reason')}")
    return payload


def _build_url(base: str, params: dict[str, Any]) -> str:
    full = {
        "hourly": ",".join(HOURLY_VARIABLES),
        "wind_speed_unit": "ms",
        "timezone": "Asia/Kolkata",
        **params,
    }
    return f"{base}?{urllib.parse.urlencode(full)}"


def fetch_forecast(
    lat: float,
    lon: float,
    *,
    urlopen: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Yesterday, today and the next two days of hourly forecast (96 hours)."""
    url = _build_url(
        FORECAST_URL,
        {"latitude": lat, "longitude": lon, "past_days": 1, "forecast_days": 3},
    )
    return _get_json(url, urlopen)


def fetch_archive(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    *,
    urlopen: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Hourly reanalysis for a past date range (inclusive, YYYY-MM-DD)."""
    url = _build_url(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    return _get_json(url, urlopen)


def parse_hourly(response: Any) -> list[dict[str, Any]]:
    """Turn an Open-Meteo response into one row per hour.

    Any measured value may be None. Raises WeatherError if the response shape
    is wrong or the variable lists do not all match the length of hourly.time.
    """
    if not isinstance(response, dict):
        raise WeatherError("response must be an object")
    hourly = response.get("hourly")
    if not isinstance(hourly, dict):
        raise WeatherError("response has no hourly block")

    times = hourly.get("time")
    if not isinstance(times, list):
        raise WeatherError("response has no hourly.time list")

    for name in HOURLY_VARIABLES:
        values = hourly.get(name)
        if not isinstance(values, list):
            raise WeatherError(f"response is missing hourly.{name}")
        if len(values) != len(times):
            raise WeatherError(
                f"hourly.{name} has {len(values)} values but hourly.time has {len(times)}"
            )

    rows: list[dict[str, Any]] = []
    for index, timestamp in enumerate(times):
        if not isinstance(timestamp, str):
            raise WeatherError(f"hourly.time[{index}] is not a string")
        row: dict[str, Any] = {"time": timestamp}
        for name, key in _ROW_KEYS.items():
            row[key] = hourly[name][index]
        rows.append(row)
    return rows


def rows_for_date(rows: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
    """The 24 rows whose time starts with date_str, in order."""
    selected = [row for row in rows if str(row.get("time", "")).startswith(f"{date_str}T")]
    if len(selected) != 24:
        raise WeatherError("date not covered")
    selected.sort(key=lambda row: row["time"])
    return selected
