import json

from copilot_core.webhook_signing import build_webhook_signature, verify_webhook_signature


def test_verify_webhook_signature_accepts_primary_and_secondary():
    body = json.dumps({"type": "mood", "data": {"mood": "relax"}}, default=str).encode(
        "utf-8"
    )
    timestamp = "1710000000"
    nonce = "abc123"

    sig_primary = build_webhook_signature(
        "primary-secret",
        body=body,
        timestamp=timestamp,
        nonce=nonce,
    )
    sig_secondary = build_webhook_signature(
        "secondary-secret",
        body=body,
        timestamp=timestamp,
        nonce=nonce,
    )

    assert verify_webhook_signature(
        secrets=["primary-secret", "secondary-secret"],
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=sig_primary,
    )

    assert verify_webhook_signature(
        secrets=["primary-secret", "secondary-secret"],
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=sig_secondary,
    )

    assert not verify_webhook_signature(
        secrets=["primary-secret"],
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=sig_secondary,
    )


def test_verify_webhook_signature_accepts_raw_hexdigest():
    body = b"{}"
    timestamp = "1710000000"
    nonce = "n"
    sig = build_webhook_signature("s", body=body, timestamp=timestamp, nonce=nonce)
    raw = sig.split("=", 1)[1]

    assert verify_webhook_signature(
        secrets=["s"],
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=raw,
    )
