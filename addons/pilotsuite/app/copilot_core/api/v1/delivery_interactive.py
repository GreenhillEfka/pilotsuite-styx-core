"""Delivery Interactive API — CORE-HARDEN-217 (303-A acknowledgment seam)

Bounded interaction contract:
  POST /api/v1/delivery/acknowledge
    body: { delivery_token: str, action: "acknowledge" | "cancel", metadata?: dict }
    response: { ok: bool, delivery_token: str, state: str, timestamp: str, metadata?: dict }

  GET /api/v1/delivery/{delivery_token}/status
    response: { delivery_token: str, state: str, created_at: str, expires_at: str }

Semantics:
  - delivery_token: opaque correlation token (UUID4, created by caller)
  - states: pending | acknowledged | cancelled | expired
  - expiry: 5 minutes from first creation
  - cancel: user-initiated stop before expiry
  - idempotent: re-acknowledge returns same state; cancel is final
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

from flask import Blueprint, jsonify, request

_LOGGER = __import__("logging").getLogger(__name__)

delivery_bp = Blueprint("delivery", __name__, url_prefix="/api/v1/delivery")

_TTL_SECONDS = 300  # 5 minutes

# In-memory store: delivery_token -> record
_store: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


class DeliveryState(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(record: dict[str, Any]) -> bool:
    return (_now() - record["created_at"]).total_seconds() > _TTL_SECONDS


def _require_auth():
    from copilot_core.api import security
    auth = getattr(security, "validate_token", None)
    if auth and auth(request):
        return None
    return jsonify({"ok": False, "error": "Unauthorized"}), 401


# ── POST /api/v1/delivery/acknowledge ─────────────────────────────────────────

@delivery_bp.route("/acknowledge", methods=["POST"])
def acknowledge_delivery():
    """Create or update a delivery token with acknowledge/cancel action.

    Idempotent: re-acknowledge of an already-acknowledged token returns the
    same state without changing anything.

    Body::
        {
            "delivery_token": str,   # UUID4, caller-generated
            "action": "acknowledge" | "cancel",
            "metadata"?: dict         # optional correlation data
        }

    Returns::
        {ok, delivery_token, state, timestamp, metadata?}
    """
    auth_err = _require_auth()
    if auth_err:
        return auth_err

    body = request.get_json(silent=True) or {}
    delivery_token = (body.get("delivery_token") or "").strip()
    action = (body.get("action") or "").strip()
    metadata = body.get("metadata")

    if not delivery_token:
        return jsonify({"ok": False, "error": "Missing field: delivery_token"}), 400
    if not action:
        return jsonify({"ok": False, "error": "Missing field: action"}), 400
    if action not in ("acknowledge", "cancel"):
        return jsonify({"ok": False, "error": f"Invalid action: {action}"}), 400

    with _lock:
        now = _now()
        existing = _store.get(delivery_token)

        if existing:
            # Cancel overrides any state (including acknowledged)
            if action == "cancel":
                existing["state"] = DeliveryState.CANCELLED.value
                existing["updated_at"] = now
                if metadata is not None:
                    existing["metadata"] = metadata
                return jsonify({
                    "ok": True,
                    "delivery_token": delivery_token,
                    "state": existing["state"],
                    "timestamp": now.isoformat(),
                    "metadata": existing.get("metadata"),
                })
            # Idempotent: already acknowledged → return same without change
            if existing["state"] == DeliveryState.ACKNOWLEDGED.value and \
                    action == "acknowledge":
                return jsonify({
                    "ok": True,
                    "delivery_token": delivery_token,
                    "state": existing["state"],
                    "timestamp": existing["updated_at"].isoformat(),
                    "metadata": existing.get("metadata"),
                })
            # Re-acknowledge pending or cancelled
            existing["state"] = DeliveryState.ACKNOWLEDGED.value
            existing["updated_at"] = now
            if metadata is not None:
                existing["metadata"] = metadata
            return jsonify({
                "ok": True,
                "delivery_token": delivery_token,
                "state": existing["state"],
                "timestamp": now.isoformat(),
                "metadata": existing.get("metadata"),
            })

        # First creation — start in the requested state
        initial_state = DeliveryState.ACKNOWLEDGED.value \
            if action == "acknowledge" \
            else DeliveryState.CANCELLED.value

        record = {
            "state": initial_state,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(seconds=_TTL_SECONDS),
            "metadata": metadata,
        }
        _store[delivery_token] = record

        return jsonify({
            "ok": True,
            "delivery_token": delivery_token,
            "state": initial_state,
            "timestamp": now.isoformat(),
            "metadata": metadata,
        })


# ── GET /api/v1/delivery/{delivery_token}/status ──────────────────────────────

@delivery_bp.route("/<delivery_token>/status", methods=["GET"])
def get_delivery_status(delivery_token: str):
    """Return current state of a delivery token.

    Returns::
        {ok, delivery_token, state, created_at, expires_at, metadata?}
    """
    auth_err = _require_auth()
    if auth_err:
        return auth_err

    if not delivery_token or not delivery_token.strip():
        return jsonify({"ok": False, "error": "Invalid delivery_token"}), 400

    with _lock:
        existing = _store.get(delivery_token)
        now = _now()

        if not existing:
            # Zero-state: unknown token is pending
            return jsonify({
                "ok": True,
                "delivery_token": delivery_token,
                "state": DeliveryState.PENDING.value,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=_TTL_SECONDS)).isoformat(),
            })

        # Expire check
        state = existing["state"]
        if state in (DeliveryState.PENDING.value, DeliveryState.ACKNOWLEDGED.value):
            if (now - existing["created_at"]).total_seconds() > _TTL_SECONDS:
                state = DeliveryState.EXPIRED.value
                existing["state"] = state

        return jsonify({
            "ok": True,
            "delivery_token": delivery_token,
            "state": state,
            "created_at": existing["created_at"].isoformat(),
            "expires_at": existing["expires_at"].isoformat(),
            "metadata": existing.get("metadata"),
        })
