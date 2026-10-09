"""WBGT from one hourly weather row (contract section 3.6).

Open-Meteo radiation values are the mean of the PRECEDING hour, so the solar
angle is evaluated 30 minutes before the hour label.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

import thermofeel

from .solar import cos_zenith

__all__ = ["compute_wbgt", "IST_OFFSET", "DEFAULT_PRESSURE_HPA"]

IST_OFFSET = timedelta(hours=5, minutes=30)
DEFAULT_PRESSURE_HPA = 1010.0
KELVIN = 273.15
# Open-Meteo reports radiation down to small values at dawn and dusk; below this
# the direct fraction is not meaningful (contract 3.6 step 2).
GHI_FLOOR_WM2 = 10.0


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return None if math.isnan(number) else number
    return None


def _scalar(result: Any) -> float:
    """thermofeel returns a numpy array; take the single value out of it."""
    try:
        return float(result[0])
    except (TypeError, IndexError):
        return float(result)


def compute_wbgt(row: dict[str, Any], lat: float, lon: float) -> tuple[float | None, str | None]:
    """WBGT in Celsius for one hourly row, rounded to one decimal.

    Returns (None, None) when temperature or humidity is missing: never guess.
    Returns method "liljegren" normally, or "simple_fallback" when wind or
    radiation is missing. Missing pressure uses DEFAULT_PRESSURE_HPA and is
    still "liljegren".
    """
    temp_c = _as_float(row.get("air_temp_c"))
    rh_pct = _as_float(row.get("rh_pct"))
    if temp_c is None or rh_pct is None:
        return None, None

    temp_k = temp_c + KELVIN
    wind_ms = _as_float(row.get("wind_ms"))
    ghi_wm2 = _as_float(row.get("ghi_wm2"))
    direct_wm2 = _as_float(row.get("direct_wm2"))

    if wind_ms is None or ghi_wm2 is None or direct_wm2 is None:
        value = _scalar(thermofeel.calculate_wbgt_simple(temp_k, rh_pct))
        if math.isnan(value):
            return None, None
        return round(value - KELVIN, 1), "simple_fallback"

    pressure_hpa = _as_float(row.get("pressure_hpa"))
    if pressure_hpa is None:
        pressure_hpa = DEFAULT_PRESSURE_HPA

    cossza = _solar_cos_for_row(row, lat, lon)
    if cossza <= 0.0:
        ssrd, fdir = 0.0, 0.0
    else:
        ssrd = ghi_wm2
        fdir = direct_wm2 / ghi_wm2 if ghi_wm2 > GHI_FLOOR_WM2 else 0.0
        fdir = max(0.0, min(1.0, fdir))

    value = _scalar(
        thermofeel.calculate_wbgt_liljegren(
            temp_k, rh_pct, pressure_hpa, wind_ms, ssrd, fdir, cossza
        )
    )
    if math.isnan(value):
        # The Liljegren iteration did not converge; fall back rather than invent.
        value = _scalar(thermofeel.calculate_wbgt_simple(temp_k, rh_pct))
        if math.isnan(value):
            return None, None
        return round(value - KELVIN, 1), "simple_fallback"

    return round(value - KELVIN, 1), "liljegren"


def _solar_cos_for_row(row: dict[str, Any], lat: float, lon: float) -> float:
    """Cosine of the zenith angle 30 minutes before the row's hour label.

    The row time is India time (contract 3.12 requests timezone=Asia/Kolkata);
    solar.cos_zenith wants naive UTC.
    """
    label_ist = datetime.strptime(str(row["time"])[:16], "%Y-%m-%dT%H:%M")
    mid_ist = label_ist - timedelta(minutes=30)
    return cos_zenith(lat, lon, mid_ist - IST_OFFSET)
