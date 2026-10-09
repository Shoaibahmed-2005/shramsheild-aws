"""Build and print today's plan for one site from the live Open-Meteo forecast.

Usage: python scripts/make_plan.py SITE_ID [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shramshield_core import weather  # noqa: E402
from shramshield_core.contract import validate_plan  # noqa: E402
from shramshield_core.plan import build_plan, india_today  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SITES_FILE = REPO_ROOT / "shared" / "fixtures" / "sites.json"


def load_site(site_id: str) -> dict:
    sites = json.loads(SITES_FILE.read_text(encoding="utf-8"))["sites"]
    for site in sites:
        if site["site_id"] == site_id:
            return site
    known = ", ".join(site["site_id"] for site in sites)
    raise SystemExit(f"unknown site {site_id!r}; known sites: {known}")


def print_table(plan: dict) -> None:
    print(f"  {'hour':>4}  {'air C':>6}  {'RH %':>5}  {'WBGT C':>7}  {'level':<8}  work")
    print(f"  {'-' * 4}  {'-' * 6}  {'-' * 5}  {'-' * 7}  {'-' * 8}  {'-' * 4}")
    for hour in plan["hours"]:
        temp = "   -  " if hour["air_temp_c"] is None else f"{hour['air_temp_c']:6.1f}"
        rh = "    -" if hour["rh_pct"] is None else f"{hour['rh_pct']:5d}"
        wbgt = "      -" if hour["wbgt_c"] is None else f"{hour['wbgt_c']:7.1f}"
        mark = "yes" if hour["in_work_hours"] else " - "
        print(f"  {hour['hour']:4d}  {temp}  {rh}  {wbgt}  {hour['level']:<8}  {mark}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_id")
    parser.add_argument("--date", dest="date", default=None, help="YYYY-MM-DD, default today in India")
    args = parser.parse_args(argv[1:])

    site = load_site(args.site_id)
    date_str = args.date or india_today()

    response = weather.fetch_forecast(site["lat"], site["lon"])
    rows = weather.rows_for_date(weather.parse_hourly(response), date_str)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    plan = build_plan(site, rows, date_str, generated_at)

    print(f"{site['name']} ({site['site_id']})  {date_str}")
    print(
        f"profile: {site['workload']} work, "
        f"{'acclimatized' if site['acclimatized'] else 'unacclimatized'}, "
        f"work hours {site['work_start_hour']} to {site['work_end_hour']}"
    )
    print(f"source: {plan['source']}")
    print()
    print_table(plan)
    print()

    summary = plan["summary"]
    print(
        f"worst level: {summary['worst_level']}   "
        f"peak WBGT: {summary['peak_wbgt_c']} C at hour {summary['peak_hour']}"
    )
    for window in summary["windows"]:
        print(
            f"  window {window['start_hour']:02d}:00 to {window['end_hour']:02d}:00  "
            f"{window['level']:<7} work {window['max_work_min']} min / "
            f"rest {window['min_rest_min']} min"
        )
    print()
    print("EN:", plan["messages"]["en"])
    print()
    print("HI:", plan["messages"]["hi"])
    print()

    errors = validate_plan(plan)
    if errors:
        print(f"validate_plan FAILED with {len(errors)} error(s):")
        for error in errors:
            print(f"  {error}")
        return 1
    print("validate_plan: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
