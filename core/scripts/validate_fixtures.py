"""Validate every file in shared/fixtures against the contract validators.

Usage: python scripts/validate_fixtures.py [fixtures_dir]
Exits 1 if any fixture has errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shramshield_core.contract import (  # noqa: E402
    validate_backtest,
    validate_plan,
    validate_run,
    validate_site,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = REPO_ROOT / "shared" / "fixtures"


def validate_sites_file(obj: object) -> list[str]:
    """sites.json wraps a list of Site objects under the key "sites"."""
    if not isinstance(obj, dict) or not isinstance(obj.get("sites"), list):
        return ['sites.json: must be an object with a "sites" list']
    errors: list[str] = []
    for index, site in enumerate(obj["sites"]):
        errors.extend(f"sites[{index}].{error}" for error in validate_site(site))
    return errors


def pick_validator(name: str):
    if name == "sites.json":
        return validate_sites_file
    if name.startswith("plan_"):
        return validate_plan
    if name.startswith("run_"):
        return validate_run
    if name.startswith("backtest"):
        return validate_backtest
    return None


def main(argv: list[str]) -> int:
    fixtures_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_FIXTURES
    if not fixtures_dir.is_dir():
        print(f"FAIL  {fixtures_dir}: not a directory")
        return 1

    paths = sorted(p for p in fixtures_dir.glob("*.json") if p.is_file())
    if not paths:
        print(f"FAIL  {fixtures_dir}: no JSON fixtures found")
        return 1

    failed = False
    for path in paths:
        validator = pick_validator(path.name)
        if validator is None:
            print(f"SKIP  {path.name}: no validator for this file name")
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL  {path.name}: could not read JSON: {exc}")
            failed = True
            continue
        errors = validator(obj)
        if errors:
            failed = True
            print(f"FAIL  {path.name}: {len(errors)} error(s)")
            for error in errors:
                print(f"        {error}")
        else:
            print(f"OK    {path.name}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
