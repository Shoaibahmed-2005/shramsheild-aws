"""Amazon Polly voice synthesis and S3 presigned URL generation."""

import logging
import os
from typing import Optional

import boto3
from botocore.config import Config

logger = logging.getLogger("voice")
logger.setLevel(logging.INFO)


def _get_polly_client() -> boto3.client:
    polly_region = os.environ.get("POLLY_REGION", "ap-south-1")
    return boto3.client("polly", region_name=polly_region)


def _get_s3_client() -> boto3.client:
    stack_region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
    cfg = Config(signature_version="s3v4")
    return boto3.client("s3", region_name=stack_region, config=cfg)


def presign_voice_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned HTTPS GET URL for a voice object in S3."""
    bucket = os.environ.get("VOICE_BUCKET")
    if not bucket:
        raise RuntimeError("VOICE_BUCKET environment variable not set")
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def synthesize(text: str, run_id: str, lang: str = "hi") -> str:
    """Synthesize speech using Amazon Polly, store in S3, and return a presigned URL.

    Uses Kajal (neural hi-IN) or Aditi (en-IN).
    Writes to voice/{run_id}_{lang}.mp3 and returns an HTTPS URL valid for 1 hour.
    """
    bucket = os.environ.get("VOICE_BUCKET")
    if not bucket:
        raise RuntimeError("VOICE_BUCKET environment variable not set")

    voice_id = os.environ.get("POLLY_VOICE_ID", "Kajal")
    engine = os.environ.get("POLLY_ENGINE", "neural")
    language_code = "hi-IN" if lang == "hi" else "en-IN"

    polly = _get_polly_client()
    logger.info("Synthesizing speech with Polly (voice: %s, engine: %s, lang: %s)", voice_id, engine, language_code)

    resp = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId=voice_id,
        Engine=engine,
        LanguageCode=language_code,
    )

    audio_stream = resp.get("AudioStream")
    if not audio_stream:
        raise RuntimeError("Polly did not return an AudioStream")

    audio_bytes = audio_stream.read()
    s3_key = f"voice/{run_id}_{lang}.mp3"

    s3 = _get_s3_client()
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=audio_bytes,
        ContentType="audio/mpeg",
    )

    return presign_voice_url(s3_key, expires_in=3600)
