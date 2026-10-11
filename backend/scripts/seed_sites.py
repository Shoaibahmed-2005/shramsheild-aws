#!/usr/bin/env python3
"""Seed demo sites into the DynamoDB table or update contact chat IDs.

Usage:
  python backend/scripts/seed_sites.py [--stack STACK_NAME] [--table TABLE_NAME] [--overwrite]
  python backend/scripts/seed_sites.py set-chat SITE_ID supervisor|backup CHAT_ID [--stack STACK_NAME] [--table TABLE_NAME]
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Optional

import boto3

# Ensure backend/src is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
src_dir = backend_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from common import db


def resolve_table_name(stack_name: str, region: str = "ap-south-1") -> str:
    """Find DynamoDB TableName from CloudFormation stack outputs."""
    cf = boto3.client("cloudformation", region_name=region)
    resp = cf.describe_stacks(StackName=stack_name)
    outputs = resp["Stacks"][0].get("Outputs", [])
    for out in outputs:
        if out["OutputKey"] == "TableName":
            return out["OutputValue"]
    raise RuntimeError(f"Could not find TableName output in stack '{stack_name}'")


def seed_sites(table: Any, sites_json_path: Path, overwrite: bool = False) -> int:
    """Read sites.json and insert sites into DynamoDB table."""
    with open(sites_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sites = data.get("sites", [])
    print(f"[seed_sites] Loaded {len(sites)} sites from {sites_json_path.name}")

    inserted = 0
    skipped = 0
    for site in sites:
        site_id = site["site_id"]
        existing = db.get_site(table, site_id)
        if existing and not overwrite:
            print(f"[seed_sites] Site '{site_id}' already exists. Skipping (use --overwrite to replace).")
            skipped += 1
            continue

        db.put_site(table, site)
        print(f"[seed_sites] Seeded site '{site_id}' ({site['name']})")
        inserted += 1

    print(f"[seed_sites] Done: {inserted} seeded, {skipped} skipped.")
    return 0


def set_chat(
    table: Any,
    site_id: str,
    role: str,
    chat_id_val: str,
) -> int:
    """Update only supervisor or backup telegram_chat_id for a given site."""
    if role not in ("supervisor", "backup"):
        print(f"[set-chat] ERROR: role must be 'supervisor' or 'backup', got '{role}'", file=sys.stderr)
        return 1

    site = db.get_site(table, site_id)
    if not site:
        print(f"[set-chat] ERROR: site '{site_id}' not found in table.", file=sys.stderr)
        return 1

    # Convert chat_id to integer if numeric, else string
    val: Any
    if chat_id_val.isdigit() or (chat_id_val.startswith("-") and chat_id_val[1:].isdigit()):
        val = int(chat_id_val)
    elif chat_id_val.lower() == "null" or chat_id_val == "":
        val = None
    else:
        val = chat_id_val

    if role not in site or not isinstance(site[role], dict):
        site[role] = {"name": role.capitalize(), "telegram_chat_id": val}
    else:
        site[role]["telegram_chat_id"] = val

    db.put_site(table, site)
    print(f"[set-chat] Updated site '{site_id}' {role}.telegram_chat_id = {val}")
    return 0


def main() -> int:
    repo_root = backend_dir.parent
    fixtures_path = repo_root / "shared" / "fixtures" / "sites.json"

    # Check for set-chat subcommand
    if len(sys.argv) > 1 and sys.argv[1] == "set-chat":
        parser = argparse.ArgumentParser(description="Set chat ID for site supervisor/backup")
        parser.add_argument("command", choices=["set-chat"])
        parser.add_argument("site_id", help="Target site_id (e.g. chn-01)")
        parser.add_argument("role", choices=["supervisor", "backup"], help="Role to update")
        parser.add_argument("chat_id", help="Telegram chat ID")
        parser.add_argument("--table", default=None, help="DynamoDB table name")
        parser.add_argument("--stack", default="shramshield", help="SAM stack name")
        parser.add_argument("--region", default="ap-south-1", help="AWS region")
        args = parser.parse_args()

        table_name = args.table or resolve_table_name(args.stack, args.region)
        dynamodb = boto3.resource("dynamodb", region_name=args.region)
        table = dynamodb.Table(table_name)
        return set_chat(table, args.site_id, args.role, args.chat_id)

    parser = argparse.ArgumentParser(description="Seed DynamoDB table with initial demo sites")
    parser.add_argument("--table", default=None, help="DynamoDB table name")
    parser.add_argument("--stack", default="shramshield", help="SAM stack name")
    parser.add_argument("--region", default="ap-south-1", help="AWS region")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing sites")
    args = parser.parse_args()

    table_name = args.table or resolve_table_name(args.stack, args.region)
    print(f"[seed_sites] Target table: {table_name}")
    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(table_name)
    return seed_sites(table, fixtures_path, overwrite=args.overwrite)


if __name__ == "__main__":
    sys.exit(main())
