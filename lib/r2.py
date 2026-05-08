"""Cloudflare R2 client wrapper. R2 is S3-compatible — uses boto3.

Env vars consumed:
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_ENDPOINT       — full URL, no trailing slash
    R2_BUCKET         — bucket name

If any of those is unset, `enabled()` returns False and callers fall back
to local-disk storage for dev workflow.
"""
import os
import logging
from typing import Optional, IO

log = logging.getLogger(__name__)

# Cache the boto3 client across calls — instantiation is non-trivial.
_client_cache = None


def enabled() -> bool:
    return all(os.environ.get(k) for k in (
        "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET"
    ))


def _client():
    global _client_cache
    if _client_cache is None:
        import boto3
        from botocore.client import Config
        _client_cache = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
    return _client_cache


def upload_fileobj(fileobj: IO[bytes], key: str, content_type: Optional[str] = None) -> bool:
    """Upload to R2 under the given key. Returns True on success, False on error."""
    if not enabled():
        return False
    extra = {"ContentType": content_type} if content_type else {}
    try:
        _client().upload_fileobj(fileobj, os.environ["R2_BUCKET"], key, ExtraArgs=extra)
        return True
    except Exception as e:
        log.warning("r2.upload_fileobj failed for %s: %s", key, e)
        return False


def presigned_url(key: str, expires: int = 3600) -> Optional[str]:
    """Return a time-limited download URL for a key, or None if R2 unavailable."""
    if not enabled() or not key:
        return None
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": os.environ["R2_BUCKET"], "Key": key},
            ExpiresIn=expires,
        )
    except Exception as e:
        log.warning("r2.presigned_url failed for %s: %s", key, e)
        return None


def head_object(key: str) -> bool:
    """True if the key exists in R2."""
    if not enabled():
        return False
    try:
        _client().head_object(Bucket=os.environ["R2_BUCKET"], Key=key)
        return True
    except Exception:
        return False


def delete_object(key: str) -> bool:
    if not enabled() or not key:
        return False
    try:
        _client().delete_object(Bucket=os.environ["R2_BUCKET"], Key=key)
        return True
    except Exception as e:
        log.warning("r2.delete_object failed for %s: %s", key, e)
        return False
