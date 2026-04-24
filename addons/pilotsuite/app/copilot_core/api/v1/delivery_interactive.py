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

from copy import deepcopy
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.v1.delivery_intent_store import DeliveryIntentStore

_LOGGER = __import__("logging").getLogger(__name__)

delivery_bp = Blueprint("delivery", __name__, url_prefix="/api/v1/delivery")

_TTL_SECONDS = 300  # 5 minutes

_intent_store = DeliveryIntentStore()
_store = _intent_store.records
_lock = _intent_store.lock


class DeliveryState(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(record: dict[str, Any]) -> bool:
    return _now() >= record["expires_at"]


def _require_auth():
    from copilot_core.api import security
    auth = getattr(security, "validate_token", None)
    if auth and auth(request):
        return None
    return jsonify({"ok": False, "error": "Unauthorized"}), 401


def _storage_error_response(error: str | None = None):
    return jsonify({
        "ok": False,
        "error": error or "Delivery intent store unavailable",
    }), 503


def _store_error() -> str | None:
    return _intent_store.last_error


def _persist_record(record: dict[str, Any]) -> bool:
    return _intent_store.put(record)


def _new_record(
    delivery_token: str,
    *,
    state: str,
    action: str,
    now: datetime,
    metadata: Any,
) -> dict[str, Any]:
    return {
        "delivery_token": delivery_token,
        "state": state,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(seconds=_TTL_SECONDS),
        "last_action": action,
        "attempt_count": 1,
        "metadata": metadata,
    }


def _increment_attempt(record: dict[str, Any]) -> None:
    record["attempt_count"] = int(record.get("attempt_count", 0)) + 1


def _post_response(record: dict[str, Any]):
    return jsonify({
        "ok": True,
        "delivery_token": record["delivery_token"],
        "state": record["state"],
        "timestamp": record["updated_at"].isoformat(),
        "metadata": record.get("metadata"),
    })


def _status_response(record: dict[str, Any]):
    return jsonify({
        "ok": True,
        "delivery_token": record["delivery_token"],
        "state": record["state"],
        "created_at": record["created_at"].isoformat(),
        "expires_at": record["expires_at"].isoformat(),
        "metadata": record.get("metadata"),
    })


def _pending_status_response(delivery_token: str, now: datetime):
    return jsonify({
        "ok": True,
        "delivery_token": delivery_token,
        "state": DeliveryState.PENDING.value,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=_TTL_SECONDS)).isoformat(),
    })


def _set_delivery_intent_store_for_testing(store: DeliveryIntentStore) -> None:
    global _intent_store, _store, _lock
    _intent_store = store
    _store = _intent_store.records
    _lock = _intent_store.lock


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
        if _store_error():
            return _storage_error_response(_store_error())

        now = _now()
        existing = _intent_store.get(delivery_token)

        if existing is None:
            initial_state = (
                DeliveryState.ACKNOWLEDGED.value
                if action == "acknowledge"
                else DeliveryState.CANCELLED.value
            )
            created = _new_record(
                delivery_token,
                state=initial_state,
                action=action,
                now=now,
                metadata=metadata,
            )
            if not _persist_record(created):
                return _storage_error_response(_store_error())
            return _post_response(created)

        if existing["state"] in (
            DeliveryState.PENDING.value,
            DeliveryState.ACKNOWLEDGED.value,
        ) and _is_expired(existing):
            expired = deepcopy(existing)
            expired["state"] = DeliveryState.EXPIRED.value
            expired["updated_at"] = now
            expired["last_action"] = action
            _increment_attempt(expired)
            if not _persist_record(expired):
                return _storage_error_response(_store_error())
            return _post_response(expired)

        if action == "cancel":
            updated = deepcopy(existing)
            updated["updated_at"] = now
            updated["last_action"] = action
            _increment_attempt(updated)
            if updated["state"] != DeliveryState.EXPIRED.value:
                updated["state"] = DeliveryState.CANCELLED.value
                if metadata is not None:
                    updated["metadata"] = metadata
            if not _persist_record(updated):
                return _storage_error_response(_store_error())
            return _post_response(updated)

        if existing["state"] == DeliveryState.ACKNOWLEDGED.value:
            return _post_response(existing)

        updated = deepcopy(existing)
        updated["updated_at"] = now
        updated["last_action"] = action
        _increment_attempt(updated)
        if updated["state"] not in (
            DeliveryState.CANCELLED.value,
            DeliveryState.EXPIRED.value,
        ):
            updated["state"] = DeliveryState.ACKNOWLEDGED.value
            if metadata is not None:
                updated["metadata"] = metadata

        if not _persist_record(updated):
            return _storage_error_response(_store_error())
        return _post_response(updated)


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
        if _store_error():
            return _storage_error_response(_store_error())

        existing = _intent_store.get(delivery_token)
        now = _now()

        if not existing:
            return _pending_status_response(delivery_token, now)

        if existing["state"] in (
            DeliveryState.PENDING.value,
            DeliveryState.ACKNOWLEDGED.value,
        ) and _is_expired(existing):
            expired = deepcopy(existing)
            expired["state"] = DeliveryState.EXPIRED.value
            expired["updated_at"] = now
            expired["last_action"] = "status"
            if not _persist_record(expired):
                return _storage_error_response(_store_error())
            existing = expired

        return _status_response(existing)
