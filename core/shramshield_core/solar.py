"""Solar geometry: cosine of the solar zenith angle.

Convention for this whole package: ``when_utc`` is a timezone-NAIVE datetime
that already holds UTC wall-clock time. Callers working in India time must
subtract 5 hours 30 minutes before calling (see ``wbgt.compute_wbgt``).
"""

from __future__ import annotations

import math
from datetime import datetime

__all__ = ["cos_zenith"]


def cos_zenith(lat_deg: float, lon_deg: float, when_utc: datetime) -> float:
    """Cosine of the solar zenith angle, clamped to 0..1.

    ``when_utc`` is interpreted as UTC. Zero means the sun is at or below the
    horizon. Follows the NOAA solar position approximation.
    """
    doy = when_utc.timetuple().tm_yday
    hour = when_utc.hour + when_utc.minute / 60 + when_utc.second / 3600
    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(g)
        - 0.032077 * math.sin(g)
        - 0.014615 * math.cos(2 * g)
        - 0.040849 * math.sin(2 * g)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(g)
        + 0.070257 * math.sin(g)
        - 0.006758 * math.cos(2 * g)
        + 0.000907 * math.sin(2 * g)
        - 0.002697 * math.cos(3 * g)
        + 0.00148 * math.sin(3 * g)
    )
    tst = hour * 60 + eqtime + 4 * lon_deg
    ha = math.radians(tst / 4 - 180)
    lat = math.radians(lat_deg)
    c = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    return max(0.0, min(1.0, c))
