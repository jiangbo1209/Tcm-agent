"""HMAC-signed file access token for backend streaming URLs."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

_TOKEN_SECRET = b"tcm-file-stream-v1"

_SECRET_KEY = hashlib.sha256(_TOKEN_SECRET).digest()


def generate_file_token(
    storage_path: str,
    file_name: str,
    disposition: str,
    expires_in: int = 3600,
) -> str:
    payload = json.dumps(
        {
            "p": storage_path,
            "n": file_name,
            "d": disposition,
            "e": int(time.time()) + expires_in,
        },
        separators=(",", ":"),
    )
    encoded = urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(_SECRET_KEY, encoded.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{encoded}.{sig}"


def validate_file_token(token: str) -> tuple[str, str, str]:
    try:
        encoded, sig = token.split(".", 1)
    except ValueError:
        raise ValueError("invalid token")

    expected_sig = hmac.new(_SECRET_KEY, encoded.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("invalid token")

    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    try:
        payload = json.loads(urlsafe_b64decode(encoded))
    except Exception:
        raise ValueError("invalid token")

    if payload["e"] < int(time.time()):
        raise ValueError("token expired")
    return payload["p"], payload["n"], payload["d"]
