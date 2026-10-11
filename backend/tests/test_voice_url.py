"""The voice URL must be signed fresh on every read (expired-link bug).

A presigned S3 URL lasts one hour and Lambda signs with temporary credentials,
so a URL stored when the supervisor was notified is dead by the time anyone
reopens the run. These tests pin the fix: the S3 object key is stored, and the
API signs a new URL each time a run is read.
"""

import importlib
import io
import json
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TABLE = "shramshield-test-voice"
BUCKET = "shramshield-test-voice-bucket"
DEMO_KEY = "test-secret-key-12345"

SITE = {
    "site_id": "chn-01",
    "name": "Chennai demo site",
    "lat": 13.085,
    "lon": 80.2101,
    "workload": "moderate",
    "acclimatized": True,
    "work_start_hour": 7,
    "work_end_hour": 18,
    "language": "hi",
    "supervisor": {"name": "Supervisor", "telegram_chat_id": None},
    "backup": {"name": "Backup", "telegram_chat_id": None},
    "ack_timeout_seconds": 900,
}


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", TABLE)
    monkeypatch.setenv("VOICE_BUCKET", BUCKET)
    monkeypatch.setenv("DEMO_KEY", DEMO_KEY)
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")
        ddb.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        boto3.client("s3", region_name="ap-south-1").create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        yield ddb.Table(TABLE)


def api_event(method, path):
    return {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"http": {"method": method, "path": path}},
        "headers": {},
        "body": None,
        "isBase64Encoded": False,
    }


def staged_run(table, run_id, voice_url=None, voice_key=None):
    from common import runs

    runs.create_run(table, run_id, "chn-01", "chn-01_2026-10-11")
    runs.update_run_stage(
        table,
        run_id,
        "WAITING_ACK",
        "primary",
        "2026-10-11T08:00:00Z",
        voice_url=voice_url,
        voice_key=voice_key,
    )


def test_object_key_layout():
    from common import voice

    assert voice.object_key("chn-01_20261011T074007", "hi") == (
        "voice/chn-01_20261011T074007_hi.mp3"
    )
    assert voice.object_key("chn-01_20261011T074007", "en").endswith("_en.mp3")


def test_object_key_is_what_synthesize_writes(table, monkeypatch):
    """synthesize must store the object at exactly object_key()."""
    from common import voice

    class FakePolly:
        def synthesize_speech(self, **kwargs):
            return {"AudioStream": io.BytesIO(b"ID3fake-mp3-bytes")}

    monkeypatch.setattr(voice, "_get_polly_client", lambda: FakePolly())
    run_id = "chn-01_20261011T090000"
    voice.synthesize("test", run_id, lang="hi")

    s3 = boto3.client("s3", region_name="ap-south-1")
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])]
    assert voice.object_key(run_id, "hi") in keys


def test_get_run_signs_a_fresh_url(table, monkeypatch):
    """The stored, stale URL must never be served when a key is present."""
    import api

    importlib.reload(api)
    from common import voice

    run_id = "chn-01_20261011T074007"
    staged_run(
        table,
        run_id,
        voice_url="https://s3.example/EXPIRED-URL",
        voice_key=voice.object_key(run_id, "hi"),
    )

    signed = []

    def fake_presign(key, expires_in=3600):
        signed.append((key, expires_in))
        return f"https://s3.example/FRESH?key={key}"

    monkeypatch.setattr(api.voice, "presign_voice_url", fake_presign)

    resp = api.handler(api_event("GET", f"/runs/{run_id}"))
    body = json.loads(resp["body"])

    assert resp["statusCode"] == 200
    assert body["voice_url"] == f"https://s3.example/FRESH?key=voice/{run_id}_hi.mp3"
    assert "EXPIRED-URL" not in body["voice_url"]
    # Signed once, and still at the one hour the contract specifies.
    assert signed == [(f"voice/{run_id}_hi.mp3", 3600)]


def test_latest_run_also_signs_a_fresh_url(table, monkeypatch):
    import api

    importlib.reload(api)
    from common import db, voice

    run_id = "chn-01_20261011T074008"
    db.put_site(table, SITE)
    staged_run(
        table,
        run_id,
        voice_url="https://s3.example/EXPIRED-URL",
        voice_key=voice.object_key(run_id, "hi"),
    )

    monkeypatch.setattr(
        api.voice, "presign_voice_url", lambda key, expires_in=3600: "https://s3.example/FRESH"
    )

    resp = api.handler(api_event("GET", "/sites/chn-01/runs/latest"))
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["voice_url"] == "https://s3.example/FRESH"


def test_legacy_run_without_a_key_is_left_alone(table, monkeypatch):
    """Runs created before voice_key existed keep their stored URL."""
    import api

    importlib.reload(api)

    run_id = "chn-01_20261011T074009"
    staged_run(table, run_id, voice_url="https://s3.example/OLD-STORED-URL")

    def explode(*args, **kwargs):
        raise AssertionError("must not sign when there is no voice_key")

    monkeypatch.setattr(api.voice, "presign_voice_url", explode)

    body = json.loads(api.handler(api_event("GET", f"/runs/{run_id}"))["body"])
    assert body["voice_url"] == "https://s3.example/OLD-STORED-URL"
    assert body.get("voice_key") is None


def test_a_signing_failure_never_breaks_the_read(table, monkeypatch):
    """If signing fails the run must still be returned, not a 500."""
    import api

    importlib.reload(api)
    from common import voice

    run_id = "chn-01_20261011T074010"
    staged_run(
        table,
        run_id,
        voice_url="https://s3.example/STALE",
        voice_key=voice.object_key(run_id, "hi"),
    )

    def boom(*args, **kwargs):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(api.voice, "presign_voice_url", boom)

    resp = api.handler(api_event("GET", f"/runs/{run_id}"))
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["voice_url"] == "https://s3.example/STALE"


def test_notify_stores_the_object_key(table):
    """The whole point: the key is persisted so it can be signed again later."""
    from common import runs, voice

    run_id = "chn-01_20261011T074011"
    staged_run(
        table,
        run_id,
        voice_url="https://s3.example/one-hour-url",
        voice_key=voice.object_key(run_id, "hi"),
    )
    stored = runs.get_run(table, run_id)
    assert stored["voice_key"] == f"voice/{run_id}_hi.mp3"


def test_the_stored_run_still_validates_against_the_contract(table):
    """voice_key is an extra field; the Run object must stay contract-valid."""
    from common import runs, voice
    from shramshield_core.contract import validate_run

    run_id = "chn-01_20261011T074012"
    staged_run(
        table,
        run_id,
        voice_url="https://s3.example/url",
        voice_key=voice.object_key(run_id, "hi"),
    )
    assert validate_run(runs.get_run(table, run_id)) == []
