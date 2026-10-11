"""DynamoDB helper functions and converters for ShramShield.

Handles single-table operations for Sites and Cached Plans,
including Decimal/float conversions and TTL handling.
"""

from decimal import Decimal
import json
import time
from typing import Any, Dict, List, Optional
from boto3.dynamodb.conditions import Attr


def to_ddb(obj: Any) -> Any:
    """Convert Python floats to Decimal recursively for DynamoDB."""
    return json.loads(json.dumps(obj), parse_float=Decimal)


def from_ddb(obj: Any) -> Any:
    """Convert DynamoDB Decimals back to int (if integral) or float."""
    if isinstance(obj, list):
        return [from_ddb(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: from_ddb(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def get_site(table: Any, site_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a Site by site_id. Returns None if not found."""
    response = table.get_item(Key={"PK": f"SITE#{site_id}", "SK": "META"})
    item = response.get("Item")
    if not item or "data" not in item:
        return None
    return from_ddb(item["data"])


def put_site(table: Any, site: Dict[str, Any]) -> None:
    """Store or update a Site in DynamoDB."""
    site_id = site["site_id"]
    table.put_item(
        Item={
            "PK": f"SITE#{site_id}",
            "SK": "META",
            "data": to_ddb(site),
        }
    )


def list_sites(table: Any) -> List[Dict[str, Any]]:
    """List all sites sorted by site_id.

    Note: The table is small (capped at 25 sites), so scanning with
    a begins_with filter on PK and equals on SK is acceptable and efficient.
    """
    filter_exp = Attr("PK").begins_with("SITE#") & Attr("SK").eq("META")
    response = table.scan(FilterExpression=filter_exp)
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression=filter_exp,
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    sites = [from_ddb(item["data"]) for item in items if "data" in item]
    sites.sort(key=lambda s: s.get("site_id", ""))
    return sites


def get_cached_plan(table: Any, site_id: str, date: str) -> Optional[Dict[str, Any]]:
    """Retrieve a cached weather plan. Returns None if missing or expired."""
    response = table.get_item(Key={"PK": f"SITE#{site_id}", "SK": f"PLAN#{date}"})
    item = response.get("Item")
    if not item or "data" not in item:
        return None

    # Check TTL explicitly in case DynamoDB automatic deletion hasn't run yet
    ttl = item.get("ttl")
    if ttl is not None and int(ttl) < int(time.time()):
        return None

    return from_ddb(item["data"])


def put_cached_plan(
    table: Any,
    site_id: str,
    date: str,
    plan: Dict[str, Any],
    ttl_seconds: int,
) -> None:
    """Store a calculated weather plan with TTL epoch timestamp."""
    ttl_epoch = int(time.time()) + int(ttl_seconds)
    table.put_item(
        Item={
            "PK": f"SITE#{site_id}",
            "SK": f"PLAN#{date}",
            "data": to_ddb(plan),
            "ttl": ttl_epoch,
        }
    )
