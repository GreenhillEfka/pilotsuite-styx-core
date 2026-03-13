"""Webhook signing helpers (stdlib only).

This module provides canonical signing + verification helpers for webhook
payloads.

Rotation model:
- Sender signs with *primary* secret.
- Receiver verifies against primary and (optionally) secondary secret, enabling
  safe key rotation.

Signature scheme:
- signing_input = f"{timestamp}.{nonce}." + body
- signature = sha256=<hex(hmac_sha256(secret, signing_input))>

Header contract (names defined in docs):
- X-Webhook-Timestamp
- X-Webhook-Nonce
- X-Webhook-Signature
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Iterable


def build_webhook_signature(
    secret: str,
    body: bytes,
    timestamp: str,
    nonce: str,
) -> str:
    """Return canonical signature string (including the `sha256=` prefix)."""
    signing_payload = f"{timestamp}.{nonce}.".encode("utf-8") + body
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(
    *,
    secrets: Iterable[str],
    body: bytes,
    timestamp: str,
    nonce: str,
    signature: str,
) -> bool:
    """Verify `signature` against any non-empty secret in `secrets`.

    Accepts both `sha256=<hex>` and raw `<hex>` signatures.
    """
    sig = (signature or "").strip()
    if not sig:
        return False

    if sig.startswith("sha256="):
        provided = sig
    else:
        # Backward/forward compatibility: treat raw hexdigest as sha256 scheme.
        provided = f"sha256={sig}"

    for secret in secrets:
        if not secret:
            continue
        expected = build_webhook_signature(
            secret,
            body=body,
            timestamp=timestamp,
            nonce=nonce,
        )
        if hmac.compare_digest(provided, expected):
            return True

    return False
