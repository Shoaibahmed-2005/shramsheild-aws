"""Set CloudWatch Logs retention on every log group belonging to the stack.

Lambda creates its log groups with retention "Never expire", which costs money
for ever. This sets a finite retention (14 days by default) on the log groups of
the stack's Lambda functions and state machine.

Usage:
    python backend/scripts/set_log_retention.py                # apply 14 days
    python backend/scripts/set_log_retention.py --dry-run       # show, change nothing
    python backend/scripts/set_log_retention.py --days 30
    python backend/scripts/set_log_retention.py --stack shramshield --region ap-south-1

Needs AWS credentials. Reads nothing secret and prints nothing secret.
"""

from __future__ import annotations

import argparse
import sys

import boto3
from botocore.exceptions import ClientError

# CloudWatch Logs only accepts these retention values.
ALLOWED_DAYS = [
    1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096,
    1827, 2192, 2557, 2922, 3288, 3653,
]

LAMBDA_TYPES = {"AWS::Lambda::Function", "AWS::Serverless::Function"}
STATE_MACHINE_TYPES = {"AWS::StepFunctions::StateMachine", "AWS::Serverless::StateMachine"}


def stack_log_groups(cfn, logs, stack_name: str) -> list[str]:
    """Log group names for the stack's Lambda functions and state machine.

    Lambda log groups follow /aws/lambda/<function name>. Step Functions only has
    a log group when logging is configured, so anything matching the stack name is
    also picked up, and missing groups are simply reported as absent.
    """
    try:
        resources = cfn.describe_stack_resources(StackName=stack_name)["StackResources"]
    except ClientError as exc:
        raise SystemExit(f"could not read stack {stack_name!r}: {exc}") from exc

    names: list[str] = []
    for resource in resources:
        physical = resource.get("PhysicalResourceId") or ""
        if resource["ResourceType"] in LAMBDA_TYPES and physical:
            names.append(f"/aws/lambda/{physical}")
        elif resource["ResourceType"] in STATE_MACHINE_TYPES and physical:
            machine = physical.rsplit(":", 1)[-1]
            names.append(f"/aws/vendedlogs/states/{machine}-Logs")

    # Catch any other log group the stack owns (vended log group names vary).
    paginator = logs.get_paginator("describe_log_groups")
    for page in paginator.paginate():
        for group in page["logGroups"]:
            name = group["logGroupName"]
            if stack_name.lower() in name.lower() and name not in names:
                names.append(name)

    return sorted(set(names))


def existing_retention(logs, name: str) -> int | None | str:
    """Current retention in days, None for never expire, or "absent"."""
    try:
        groups = logs.describe_log_groups(logGroupNamePrefix=name)["logGroups"]
    except ClientError as exc:
        return f"error: {exc.response['Error']['Code']}"
    for group in groups:
        if group["logGroupName"] == name:
            return group.get("retentionInDays")
    return "absent"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", default="shramshield")
    parser.add_argument("--region", default=None, help="default: the configured region")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.days not in ALLOWED_DAYS:
        print(f"--days must be one of {ALLOWED_DAYS}")
        return 2

    session = boto3.session.Session(region_name=args.region)
    region = session.region_name
    if not region:
        print("no region configured; pass --region or run aws configure")
        return 2

    cfn = session.client("cloudformation")
    logs = session.client("logs")

    print(f"stack {args.stack}  region {region}  target retention {args.days} days")
    if args.dry_run:
        print("DRY RUN: nothing will be changed")
    print()

    names = stack_log_groups(cfn, logs, args.stack)
    if not names:
        print("no log groups found for this stack")
        return 1

    header = f"{'log group':<70} {'before':>12} {'after':>12}"
    print(header)
    print("-" * len(header))

    changed = failed = 0
    for name in names:
        before = existing_retention(logs, name)
        if before == "absent":
            # A function that has never been invoked has no log group yet.
            print(f"{name:<70} {'absent':>12} {'skipped':>12}")
            continue
        if isinstance(before, str):
            print(f"{name:<70} {before:>12} {'skipped':>12}")
            failed += 1
            continue
        if before == args.days:
            print(f"{name:<70} {str(before):>12} {'unchanged':>12}")
            continue
        shown_before = "never" if before is None else str(before)
        if args.dry_run:
            print(f"{name:<70} {shown_before:>12} {'would set':>12}")
            continue
        try:
            logs.put_retention_policy(logGroupName=name, retentionInDays=args.days)
        except ClientError as exc:
            print(f"{name:<70} {shown_before:>12} {'FAILED':>12}")
            print(f"    {exc.response['Error']['Code']}: {exc.response['Error']['Message']}")
            failed += 1
            continue
        print(f"{name:<70} {shown_before:>12} {str(args.days):>12}")
        changed += 1

    print()
    print(f"log groups found {len(names)}, changed {changed}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
