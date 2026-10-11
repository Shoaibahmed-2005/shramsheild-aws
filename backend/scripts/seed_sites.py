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
    chat_id_val: Any,
) -> int:
    """Update only supervisor or backup telegram_chat_id for an existing site.

    Stores telegram_chat_id as an integer. Fails clearly if site does not exist.
    Never overwrites other fields.
    """
    if role not in ("supervisor", "backup"):
        print(f"[set-chat] ERROR: role must be 'supervisor' or 'backup', got '{role}'", file=sys.stderr)
        return 1

    try:
        chat_id_int = int(chat_id_val)
    except (ValueError, TypeError):
        print(f"[set-chat] ERROR: CHAT_ID must be an integer, got '{chat_id_val}'", file=sys.stderr)
        return 1

    site = db.get_site(table, site_id)
    if not site:
        print(f"[set-chat] ERROR: site '{site_id}' does not exist in table.", file=sys.stderr)
        return 1

    # Preserve all other fields and only update role.telegram_chat_id
    if role not in site or not isinstance(site[role], dict):
        site[role] = {"name": role.capitalize(), "telegram_chat_id": chat_id_int}
    else:
        site[role]["telegram_chat_id"] = chat_id_int

    db.put_site(table, site)
    print(f"[set-chat] Updated site '{site_id}' {role}.telegram_chat_id = {chat_id_int}")
    return 0


def main(argv=None) -> int:
    repo_root = backend_dir.parent
    fixtures_path = repo_root / "shared" / "fixtures" / "sites.json"

    parser = argparse.ArgumentParser(description="Seed demo sites into DynamoDB or update contact chat IDs")
    parser.add_argument("--stack", default="shramshield", help="SAM stack name (default: shramshield)")
    parser.add_argument("--table", default=None, help="DynamoDB table name")
    parser.add_argument("--region", default="ap-south-1", help="AWS region (default: ap-south-1)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing sites")

    subparsers = parser.add_subparsers(dest="command")

    # set-chat subcommand
    chat_parser = subparsers.add_parser("set-chat", help="Set supervisor or backup telegram_chat_id")
    chat_parser.add_argument("site_id", help="Target site_id (e.g. chn-01)")
    chat_parser.add_argument("role", choices=["supervisor", "backup"], help="Role to update (supervisor or backup)")
    chat_parser.add_argument("chat_id", help="Telegram chat ID (integer)")
    chat_parser.add_argument("--stack", default=argparse.SUPPRESS, help="SAM stack name")
    chat_parser.add_argument("--table", default=argparse.SUPPRESS, help="DynamoDB table name")
    chat_parser.add_argument("--region", default=argparse.SUPPRESS, help="AWS region")

    args = parser.parse_args(argv)

    table_name = args.table or resolve_table_name(args.stack, args.region)
    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    table = dynamodb.Table(table_name)

    if args.command == "set-chat":
        return set_chat(table, args.site_id, args.role, args.chat_id)
    else:
        print(f"[seed_sites] Target table: {table_name}")
        return seed_sites(table, fixtures_path, overwrite=args.overwrite)


if __name__ == "__main__":
    sys.exit(main())
