"""Observability API — CORE-E2E-OBS-305 checkpoint proof chain.

Proof chain: trigger → decision → delivery attempt → HA-confirmation
Output: structured JSON proof artifact per delivery_token.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from flask import Blueprint, jsonify, request

_LOGGER = __import__("logging").getLogger(__name__)

observability_bp = Blueprint(
    "observability",
    __name__,
    url_prefix="/api/v1/observability",
)


class CheckpointType(str, Enum):
    TRIGGER = "trigger"
    DECISION = "decision"
    DELIVERY_ATTEMPTED = "delivery_attempted"
    DELIVERY_CONFIRMED = "delivery_confirmed"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Checkpoint:
    """Single checkpoint in a delivery proof chain."""

    def __init__(self, type: str, timestamp: datetime, metadata: dict | None = None):
        self.type = type
        self.timestamp = timestamp
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            **self.metadata,
        }


class DeliveryProofBuilder:
    """Builds a structured delivery proof chain artifact."""

    def __init__(
        self,
        token: str,
        state: str = "pending",
        created_at: datetime | None = None,
    ):
        self.token = token
        self.state = state
        self.created_at = created_at or datetime.now(timezone.utc)
        self.checkpoints: list[Checkpoint] = []

    def add(self, checkpoint_type: CheckpointType, metadata: dict | None = None) -> None:
        self.checkpoints.append(
            Checkpoint(checkpoint_type.value, datetime.now(timezone.utc), metadata)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_token": self.token,
            "state": self.state,
            "created_at": self.created_at.isoformat(),
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
        }


# ── Dependency on delivery_interactive (lazy import to avoid circular dependency)

_delivery_bp_loaded = False
_delivery_store = None
_delivery_lock = None
_DeliveryState = None


def _get_delivery_deps():
    global _delivery_store, _delivery_lock, _DeliveryState
    if _delivery_store is None:
        from copilot_core.api.v1.delivery_interactive import (
            _store,
            _lock,
            DeliveryState as DS,
        )
        _delivery_store = _store
        _delivery_lock = _lock
        _DeliveryState = DS
    return _delivery_store, _delivery_lock, _DeliveryState


def _build_proof(delivery_token: str, record: dict[str, Any] | None) -> dict[str, Any]:
    store, _lock, DeliveryState = _get_delivery_deps()
    state = DeliveryState.PENDING.value
    created_at = datetime.now(timezone.utc)
    checkpoints: list[dict[str, Any]] = []

    if record:
        state = record.get("state", DeliveryState.PENDING.value)
        created_at = record.get("created_at", created_at)
        last_action = record.get("last_action", "")

        if last_action:
            cp_map = {
                "acknowledge": CheckpointType.ACKNOWLEDGED,
                "cancel": CheckpointType.CANCELLED,
            }
            cp_type = cp_map.get(last_action, CheckpointType.DELIVERY_ATTEMPTED)
            checkpoints.append(
                Checkpoint(cp_type.value, record.get("updated_at", datetime.now(timezone.utc))).to_dict()
            )

    return {
        "delivery_token": delivery_token,
        "state": state,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        "checkpoints": checkpoints,
    }


# ── GET /api/v1/delivery/{delivery_token}/proof ───────────────────────────────

def _register_delivery_proof_route():
    """Dynamically add /delivery/{token}/proof to delivery_interactive blueprint.

    This is registered at app startup via core_setup.
    """
    from copilot_core.api.v1.delivery_interactive import delivery_bp
    from flask import jsonify

    @delivery_bp.route("/<delivery_token>/proof", methods=["GET"])
    def get_delivery_proof(delivery_token: str):
        """Return structured proof chain for a delivery token.

        Query params:
            delivery_token: str

        Returns::
            {delivery_token, state, created_at, checkpoints: [...]}
        """
        from copilot_core.api import security
        auth = getattr(security, "validate_token", None)
        if not (auth and auth(request)):
            return jsonify({"ok": False, "error": "Unauthorized"}), 401

        if not delivery_token or not delivery_token.strip():
            return jsonify({"ok": False, "error": "Invalid delivery_token"}), 400

        store, _lock, DeliveryState = _get_delivery_deps()
        with _lock:
            record = store.get(delivery_token)

        proof = _build_proof(delivery_token, record)
        return jsonify({"ok": True, **proof})


_register_delivery_proof_route()


# ── GET /api/v1/observability/delivery-proof ──────────────────────────────────

@observability_bp.route("/delivery-proof", methods=["GET"])
def get_delivery_proof_observability():
    """Observability view of delivery proof chain.

    Query params:
        delivery_token: str

    Returns::
        {ok, delivery_token, state, created_at, checkpoints: [...]}
    """
    from copilot_core.api import security
    auth = getattr(security, "validate_token", None)
    if not (auth and auth(request)):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    delivery_token = (request.args.get("delivery_token") or "").strip()
    if not delivery_token:
        return jsonify({"ok": False, "error": "Missing query param: delivery_token"}), 400

    store, _lock, DeliveryState = _get_delivery_deps()
    with _lock:
        record = store.get(delivery_token)

    proof = _build_proof(delivery_token, record)
    return jsonify({"ok": True, **proof})
