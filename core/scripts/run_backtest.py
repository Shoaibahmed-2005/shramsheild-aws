"""Run the WBGT-vs-air-temperature backtest on real Open-Meteo archive data.

Usage: python scripts/run_backtest.py [--start 2024-04-01] [--end 2024-06-30]
                                      [--workload moderate] [--acclimatized true]
                                      [--work-start 7] [--work-end 18] [--refresh]

Raw archive responses are cached under core/data/raw/ so re-runs do not call
the network. Output goes to core/data/backtest/backtest.json (and is copied to
shared/fixtures/backtest.json) plus core/data/backtest/sensitivity.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import thermofeel  # noqa: E402

from shramshield_core import weather  # noqa: E402
from shramshield_core.backtest import (  # noqa: E402
    DANGEROUS_LEVELS,
    DEFAULT_THRESHOLDS_C,
    WIND_FLOOR_MS,
    REQUIRED_CAVEATS,
    backtest_site,
    combine_totals,
    rate_hours,
)
from shramshield_core.contract import validate_backtest  # noqa: E402

CORE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CORE_ROOT.parent
SITES_FILE = REPO_ROOT / "shared" / "fixtures" / "sites.json"
RAW_DIR = CORE_ROOT / "data" / "raw"
OUT_DIR = CORE_ROOT / "data" / "backtest"
SHARED_BACKTEST = REPO_ROOT / "shared" / "fixtures" / "backtest.json"

MAX_CACHE_MB = 2.0


def parse_bool(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in ("true", "yes", "1"):
        return True
    if lowered in ("false", "no", "0"):
        return False
    raise argparse.ArgumentTypeError(f"expected true or false, got {text!r}")


def load_sites() -> list[dict]:
    return json.loads(SITES_FILE.read_text(encoding="utf-8"))["sites"]


def cache_path(site_id: str, start: str, end: str) -> Path:
    return RAW_DIR / f"archive_{site_id}_{start}_{end}.json"


def get_archive(site: dict, start: str, end: str, *, refresh: bool) -> dict:
    """Fetch the archive response, or read the committed cache file."""
    path = cache_path(site["site_id"], start, end)
    if path.exists() and not refresh:
        print(f"  cache   {path.name} ({path.stat().st_size / 1024:.0f} KB)")
        return json.loads(path.read_text(encoding="utf-8"))

    print(f"  fetch   {site['site_id']} {start} to {end} from the Open-Meteo archive")
    response = weather.fetch_archive(site["lat"], site["lon"], start, end)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(response, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    print(f"  saved   {path.name} ({path.stat().st_size / 1024:.0f} KB)")
    return response


def report_nulls(site_id: str, rows: list[dict]) -> dict[str, int]:
    keys = ["air_temp_c", "rh_pct", "pressure_hpa", "wind_ms", "ghi_wm2", "direct_wm2"]
    counts = {key: sum(1 for row in rows if row[key] is None) for key in keys}
    if any(counts.values()):
        shown = ", ".join(f"{key}={value}" for key, value in counts.items() if value)
        print(f"  nulls   {site_id}: {shown}")
    else:
        print(f"  nulls   {site_id}: none")
    return counts


def print_summary(result: dict) -> None:
    print()
    print("=" * 78)
    print("BACKTEST SUMMARY")
    print(
        f"period {result['period']['start']} to {result['period']['end']}   "
        f"profile {result['profile']['workload']}, "
        f"{'acclimatized' if result['profile']['acclimatized'] else 'unacclimatized'}, "
        f"work hours {result['profile']['work_start_hour']} to {result['profile']['work_end_hour']}"
    )
    print(f"dangerous = work hour at level {' or '.join(DANGEROUS_LEVELS)}")
    print("=" * 78)

    header = (
        f"{'site':<22} {'work hrs':>8} {'danger':>7} {'thr':>4} "
        f"{'alert':>6} {'caught':>7} {'missed':>7} {'missed %':>9} {'false':>6}"
    )
    print(header)
    print("-" * len(header))

    for site in result["sites"]:
        label = f"{site['name']} ({site['site_id']})"
        for index, row in enumerate(site["by_threshold"]):
            left = (
                f"{label:<22} {site['work_hours_with_data']:>8} {site['dangerous_hours']:>7}"
                if index == 0
                else f"{'':<22} {'':>8} {'':>7}"
            )
            print(
                f"{left} {row['threshold_c']:>4} {row['alert_hours']:>6} "
                f"{row['caught']:>7} {row['missed']:>7} {row['missed_pct']:>8.1f}% "
                f"{row['false_alarm_hours']:>6}"
            )
        print("-" * len(header))

    totals = result["totals"]
    for index, row in enumerate(totals["by_threshold"]):
        left = (
            f"{'ALL SITES':<22} {'':>8} {totals['dangerous_hours']:>7}"
            if index == 0
            else f"{'':<22} {'':>8} {'':>7}"
        )
        print(
            f"{left} {row['threshold_c']:>4} {row['alert_hours']:>6} "
            f"{row['caught']:>7} {row['missed']:>7} {row['missed_pct']:>8.1f}% "
            f"{row['false_alarm_hours']:>6}"
        )
    print("=" * 78)

    print()
    print("LEVEL COUNTS (work hours)")
    for site in result["sites"]:
        counts = site["level_counts"]
        shown = "  ".join(f"{level} {counts[level]}" for level in counts)
        print(f"  {site['site_id']}: {shown}")

    print()
    print("EXAMPLE HOURS (coolest dangerous work hour per site)")
    for site in result["sites"]:
        example = site["example_hour"]
        if example is None:
            print(f"  {site['site_id']}: none")
        else:
            print(
                f"  {site['site_id']}: {example['time']}  air {example['air_temp_c']} C  "
                f"RH {example['rh_pct']} %  WBGT {example['wbgt_c']} C  {example['level']}"
            )


def sanity_checks(result: dict, rated_by_site: dict[str, list[dict]]) -> bool:
    """Print PASS or FAIL for each check in step 4. Returns True if all pass."""
    print()
    print("=" * 78)
    print("SANITY CHECKS")
    print("=" * 78)
    ok = True

    by_id = {site["site_id"]: site for site in result["sites"]}

    chennai = by_id.get("chn-01")
    passed = chennai is not None and chennai["dangerous_hours"] > 0
    ok &= passed
    print(
        f"  {'PASS' if passed else 'FAIL'}  Chennai has more than zero dangerous hours "
        f"({chennai['dangerous_hours'] if chennai else 'missing'})"
    )

    delhi_rated = rated_by_site.get("del-01", [])
    delhi_hot = [
        hour
        for hour in delhi_rated
        if hour["level"] in DANGEROUS_LEVELS and hour["time"][5:7] in ("05", "06")
    ]
    passed = len(delhi_hot) > 0
    ok &= passed
    print(
        f"  {'PASS' if passed else 'FAIL'}  Delhi has RED or STOP hours in May or June "
        f"({len(delhi_hot)} hours)"
    )

    night_bad = [
        (site_id, hour["time"], hour["level"], hour["wbgt_c"])
        for site_id, rated in rated_by_site.items()
        for hour in rated
        if hour["level"] in DANGEROUS_LEVELS and not 6 <= hour["hour"] <= 19
    ]
    passed = not night_bad
    ok &= passed
    print(
        f"  {'PASS' if passed else 'FAIL'}  no night hour (before 06:00 or after 19:00) "
        f"is RED or STOP ({len(night_bad)} found)"
    )
    for entry in night_bad[:10]:
        print(f"          {entry}")

    exceeds = [
        (site_id, hour["time"], hour["air_temp_c"], hour["wbgt_c"], hour["wind_ms"])
        for site_id, rated in rated_by_site.items()
        for hour in rated
        if hour["wbgt_c"] is not None
        and hour["air_temp_c"] is not None
        and hour["wbgt_c"] > hour["air_temp_c"] + 3
    ]
    # Below Liljegren's wind floor the convective term is saturated and a sunlit
    # globe genuinely runs far above air temperature, so those hours are listed
    # rather than treated as implausible. Everything else must stay within +3 C.
    becalmed = [entry for entry in exceeds if entry[4] is not None and entry[4] < WIND_FLOOR_MS]
    implausible = [entry for entry in exceeds if entry not in becalmed]
    passed = not implausible
    ok &= passed
    print(
        f"  {'PASS' if passed else 'FAIL'}  WBGT never exceeds air temperature + 3 C at "
        f"wind >= {WIND_FLOOR_MS} m/s ({len(implausible)} hours)"
    )
    for entry in implausible[:10]:
        print(
            f"          site {entry[0]} {entry[1]} air {entry[2]} C wbgt {entry[3]} C "
            f"wind {entry[4]} m/s"
        )
    if len(implausible) > 10:
        print(f"          ... and {len(implausible) - 10} more")
    print(
        f"  NOTE  {len(becalmed)} hour(s) exceed +3 C at wind below the "
        f"{WIND_FLOOR_MS} m/s Liljegren floor (near-calm, expected; see docs/METHOD.md):"
    )
    for entry in becalmed:
        print(
            f"          site {entry[0]} {entry[1]} air {entry[2]} C wbgt {entry[3]} C "
            f"wind {entry[4]} m/s"
        )

    print("=" * 78)
    return bool(ok)


def build_sensitivity(sites: list[dict], rows_by_site: dict[str, list[dict]], args) -> dict:
    """Dangerous hours and missed percent at 40 C for two other profiles."""
    variants = [
        {"workload": "heavy", "acclimatized": True},
        {"workload": "moderate", "acclimatized": False},
    ]
    out = {
        "_note": (
            "Robustness check, not part of the shared contract. Same data and period "
            "as backtest.json, different work profile."
        ),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period": {"start": args.start, "end": args.end},
        "baseline_threshold_c": 40,
        "variants": [],
    }
    for variant in variants:
        entries = [
            backtest_site(
                site,
                rows_by_site[site["site_id"]],
                workload=variant["workload"],
                acclimatized=variant["acclimatized"],
                work_start_hour=args.work_start,
                work_end_hour=args.work_end,
            )
            for site in sites
        ]
        totals = combine_totals(entries)
        at_40 = next(row for row in totals["by_threshold"] if row["threshold_c"] == 40)
        out["variants"].append(
            {
                "workload": variant["workload"],
                "acclimatized": variant["acclimatized"],
                "dangerous_hours": totals["dangerous_hours"],
                "missed_at_40c": at_40["missed"],
                "missed_pct_at_40c": at_40["missed_pct"],
                "sites": [
                    {
                        "site_id": entry["site_id"],
                        "dangerous_hours": entry["dangerous_hours"],
                        "missed_pct_at_40c": next(
                            row
                            for row in entry["by_threshold"]
                            if row["threshold_c"] == 40
                        )["missed_pct"],
                    }
                    for entry in entries
                ],
            }
        )
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-04-01")
    parser.add_argument("--end", default="2024-06-30")
    parser.add_argument("--workload", default="moderate")
    parser.add_argument("--acclimatized", type=parse_bool, default=True)
    parser.add_argument("--work-start", dest="work_start", type=int, default=7)
    parser.add_argument("--work-end", dest="work_end", type=int, default=18)
    parser.add_argument("--refresh", action="store_true", help="re-download the archive data")
    args = parser.parse_args(argv[1:])

    sites = load_sites()
    print(f"Backtest {args.start} to {args.end} for {len(sites)} sites")
    print()

    expected_hours = (
        datetime.strptime(args.end, "%Y-%m-%d") - datetime.strptime(args.start, "%Y-%m-%d")
    ).days + 1
    expected_rows = expected_hours * 24

    rows_by_site: dict[str, list[dict]] = {}
    for site in sites:
        response = get_archive(site, args.start, args.end, refresh=args.refresh)
        rows = weather.parse_hourly(response)
        if len(rows) != expected_rows:
            print(
                f"FAIL  {site['site_id']}: expected {expected_rows} hourly rows "
                f"({expected_hours} days x 24), got {len(rows)}"
            )
            return 1
        print(f"  rows    {site['site_id']}: {len(rows)} hours ({expected_hours} days x 24)")
        report_nulls(site["site_id"], rows)
        rows_by_site[site["site_id"]] = rows

    oversized = [
        path.name
        for path in sorted(RAW_DIR.glob("archive_*.json"))
        if path.stat().st_size / (1024 * 1024) > MAX_CACHE_MB
    ]
    print()
    print("CACHE FILE SIZES")
    for path in sorted(RAW_DIR.glob("archive_*.json")):
        print(f"  {path.stat().st_size / 1024:>7.0f} KB  {path.name}")
    if oversized:
        print(f"  NOTE: above {MAX_CACHE_MB} MB, tell the human before committing: {oversized}")

    entries = [
        backtest_site(
            site,
            rows_by_site[site["site_id"]],
            workload=args.workload,
            acclimatized=args.acclimatized,
            work_start_hour=args.work_start,
            work_end_hour=args.work_end,
        )
        for site in sites
    ]
    rated_by_site = {
        site["site_id"]: rate_hours(
            rows_by_site[site["site_id"]],
            site["lat"],
            site["lon"],
            workload=args.workload,
            acclimatized=args.acclimatized,
        )
        for site in sites
    }

    result = {
        "_fixture": False,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period": {"start": args.start, "end": args.end},
        "profile": {
            "workload": args.workload,
            "acclimatized": args.acclimatized,
            "work_start_hour": args.work_start,
            "work_end_hour": args.work_end,
        },
        "dangerous_levels": list(DANGEROUS_LEVELS),
        "baseline_thresholds_c": list(DEFAULT_THRESHOLDS_C),
        "sites": entries,
        "totals": combine_totals(entries),
        "caveats": list(REQUIRED_CAVEATS),
        "sources": {
            "weather": "Open-Meteo archive (ERA5 based reanalysis)",
            "wbgt_method": "liljegren",
            "thermofeel": thermofeel.__version__,
        },
    }

    print_summary(result)
    checks_ok = sanity_checks(result, rated_by_site)

    errors = validate_backtest(result)
    print()
    if errors:
        print(f"validate_backtest FAILED with {len(errors)} error(s):")
        for error in errors:
            print(f"  {error}")
        return 1
    print("validate_backtest: OK")

    if not checks_ok:
        print()
        print("A sanity check FAILED. Nothing was written. Tell the human.")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "backtest.json"
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    shutil.copyfile(out_path, SHARED_BACKTEST)
    print(f"wrote {out_path.relative_to(REPO_ROOT)}")
    print(f"wrote {SHARED_BACKTEST.relative_to(REPO_ROOT)}")

    sensitivity = build_sensitivity(sites, rows_by_site, args)
    sens_path = OUT_DIR / "sensitivity.json"
    with sens_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(sensitivity, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"wrote {sens_path.relative_to(REPO_ROOT)}")

    print()
    print("SENSITIVITY (dangerous hours and missed % at 40 C)")
    for variant in sensitivity["variants"]:
        state = "acclimatized" if variant["acclimatized"] else "unacclimatized"
        print(
            f"  {variant['workload']:<11} {state:<15} dangerous {variant['dangerous_hours']:>5}  "
            f"missed {variant['missed_pct_at_40c']:>5.1f}%"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
