"""ACGIH screening limits: WBGT to a work/rest band (contract section 3.7)."""

from __future__ import annotations

from typing import Any

from .contract import LEVEL_FOR_BAND, LIMITS_C, MAX_WORK_MIN

__all__ = ["classify", "BANDS", "BAND_LABELS"]

BANDS: tuple[str, ...] = ("A", "B", "C", "D")

BAND_LABELS: dict[str, str] = {
    "A": "75-100%",
    "B": "50-75%",
    "C": "25-50%",
    "D": "0-25%",
}

UNKNOWN_REASON = "Temperature or humidity data missing for this hour; no advice given."

# WBGT is carried to one decimal, so this only absorbs float representation error.
_EPS = 1e-9


def _table(workload: str, acclimatized: bool) -> dict[str, float | None]:
    state = "acclimatized" if acclimatized else "unacclimatized"
    try:
        return LIMITS_C[state][workload]
    except KeyError as exc:
        raise ValueError(f"unknown workload {workload!r}") from exc


def classify(wbgt_c: float | None, workload: str, acclimatized: bool) -> dict[str, Any]:
    """Pick the work/rest band for a WBGT value.

    Takes the first band in A, B, C, D order whose limit is listed and where
    wbgt_c is at or below it. If none fits the level is STOP.
    """
    table = _table(workload, acclimatized)
    state = "acclimatized" if acclimatized else "unacclimatized"

    if wbgt_c is None:
        return {
            "level": "UNKNOWN",
            "max_work_min": None,
            "min_rest_min": None,
            "limit_c": None,
            "reason": UNKNOWN_REASON,
        }

    available = [band for band in BANDS if table[band] is not None]
    first_available = available[0] if available else None

    for band in BANDS:
        limit = table[band]
        if limit is None or wbgt_c > limit + _EPS:
            continue
        level = LEVEL_FOR_BAND[band]
        reason = (
            f"WBGT {wbgt_c:.1f} C is within the {limit:.1f} C limit for "
            f"{BAND_LABELS[band]} work ({workload} work, {state})."
        )
        if band == first_available and band != "A":
            # heavy and very_heavy have no limit for the most permissive bands,
            # so the best level reachable at this workload is capped.
            reason += (
                " The table lists no limit for more permissive bands at this "
                f"workload, so the best level is capped at {level}."
            )
        return {
            "level": level,
            "max_work_min": MAX_WORK_MIN[level],
            "min_rest_min": 60 - MAX_WORK_MIN[level],
            "limit_c": limit,
            "reason": reason,
        }

    highest = max(limit for limit in table.values() if limit is not None)
    return {
        "level": "STOP",
        "max_work_min": 0,
        "min_rest_min": 60,
        "limit_c": None,
        "reason": (
            f"WBGT {wbgt_c:.1f} C is above every screening limit for "
            f"{workload} work ({state}); highest limit is {highest:.1f} C."
        ),
    }
