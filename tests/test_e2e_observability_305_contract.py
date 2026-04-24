"""E2E Observability — CORE-E2E-OBS-305 checkpoint proof chain

Proof chain: trigger → decision → delivery attempt → HA-confirmation
Output: structured JSON proof artifact per delivery_token
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.delivery_interactive import (
    delivery_bp,
    _set_delivery_intent_store_for_testing,
    _store,
    _lock,
    _TTL_SECONDS,
    DeliveryState,
)
from copilot_core.api.v1.delivery_intent_store import DeliveryIntentStore
from copilot_core.api.v1.observability import observability_bp, CheckpointType, DeliveryProofBuilder
from unittest.mock import patch
import copilot_core.api.security as security


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(delivery_bp)
    app.register_blueprint(observability_bp)
    return app


def _with_auth():
    return patch('copilot_core.api.security.validate_token', return_value=True)


def _make_token() -> str:
    return str(uuid.uuid4())


# ── Core proof chain contract tests ───────────────────────────────────────────

class TestObservabilityCheckpointChain:
    """Prove: trigger → decision → delivery → HA-confirmation per delivery_token."""

    def test_checkpoint_requires_auth(self):
        token = _make_token()
        r = _make_app().test_client().get(f"/api/v1/delivery/{token}/proof")
        assert r.status_code in (401, 403)

    def test_proof_unknown_token_returns_empty_chain(self):
        """An unknown token returns empty chain with zero-state metadata."""
        app = _make_app()
        with _with_auth():
            d = app.test_client().get(f"/api/v1/delivery/{_make_token()}/proof").get_json()
            assert "delivery_token" in d
            assert "checkpoints" in d
            assert len(d["checkpoints"]) == 0
            assert d["state"] == DeliveryState.PENDING.value

    def test_proof_reflects_acknowledged_state(self):
        """Acknowledge creates a checkpoint in the proof chain."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                  json={"delivery_token": token, "action": "acknowledge"})
            d = c.get(f"/api/v1/delivery/{token}/proof").get_json()
            assert d["delivery_token"] == token
            assert d["state"] == DeliveryState.ACKNOWLEDGED.value
            # Has at least one checkpoint: acknowledge
            assert len(d["checkpoints"]) >= 1
            assert d["checkpoints"][0]["type"] == CheckpointType.ACKNOWLEDGED.value

    def test_proof_reflects_cancelled_state(self):
        """Cancel creates a checkpoint in the proof chain."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                  json={"delivery_token": token, "action": "cancel"})
            d = c.get(f"/api/v1/delivery/{token}/proof").get_json()
            assert d["state"] == DeliveryState.CANCELLED.value
            assert len(d["checkpoints"]) >= 1
            assert d["checkpoints"][0]["type"] == CheckpointType.CANCELLED.value

    def test_proof_chain_contains_timestamps(self):
        """Each checkpoint has a timestamp; proof has created_at."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                  json={"delivery_token": token, "action": "acknowledge"})
            d = c.get(f"/api/v1/delivery/{token}/proof").get_json()
            assert "created_at" in d
            for cp in d["checkpoints"]:
                assert "timestamp" in cp

    def test_proof_chain_is_ordered(self):
        """Checkpoints are ordered by timestamp."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                  json={"delivery_token": token, "action": "acknowledge"})
            c.post("/api/v1/delivery/acknowledge",
                  json={"delivery_token": token, "action": "cancel"})
            d = c.get(f"/api/v1/delivery/{token}/proof").get_json()
            timestamps = [cp["timestamp"] for cp in d["checkpoints"]]
            assert timestamps == sorted(timestamps)

    def test_proof_shows_full_lifecycle(self):
        """Full acknowledge → cancel lifecycle has correct checkpoint sequence."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                  json={"delivery_token": token, "action": "acknowledge"})
            c.post("/api/v1/delivery/acknowledge",
                  json={"delivery_token": token, "action": "cancel"})
            d = c.get(f"/api/v1/delivery/{token}/proof").get_json()
            types = [cp["type"] for cp in d["checkpoints"]]
            # Last checkpoint should be CANCELLED (cancel is final state)
            assert types[-1] == CheckpointType.CANCELLED.value
            # State at head of chain is cancelled
            assert d["state"] == DeliveryState.CANCELLED.value


class TestObservabilityEndpoint:
    """GET /api/v1/observability/delivery-proof."""

    def test_proof_endpoint_requires_auth(self):
        r = _make_app().test_client().get("/api/v1/observability/delivery-proof")
        assert r.status_code in (401, 403)

    def test_proof_endpoint_returns_structure(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            # acknowledge first
            app.test_client().post("/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"})
            d = app.test_client().get(
                f"/api/v1/observability/delivery-proof?delivery_token={token}"
            ).get_json()
            assert "ok" in d or "error" not in d


class TestDeliveryProofBuilder:
    """Unit test for DeliveryProofBuilder."""

    def test_builder_defaults(self):
        builder = DeliveryProofBuilder("tok_123")
        assert builder.token == "tok_123"
        assert builder.state == DeliveryState.PENDING.value
        assert len(builder.checkpoints) == 0

    def test_builder_add_checkpoint(self):
        builder = DeliveryProofBuilder("tok_123")
        builder.add(CheckpointType.DELIVERY_ATTEMPTED)
        assert len(builder.checkpoints) == 1
        assert builder.checkpoints[0].type == CheckpointType.DELIVERY_ATTEMPTED

    def test_builder_to_dict(self):
        builder = DeliveryProofBuilder("tok_abc")
        builder.add(CheckpointType.TRIGGER)
        builder.add(CheckpointType.DELIVERY_ATTEMPTED)
        d = builder.to_dict()
        assert d["delivery_token"] == "tok_abc"
        assert d["state"] == DeliveryState.PENDING.value
        assert len(d["checkpoints"]) == 2

    def test_builder_known_state(self):
        builder = DeliveryProofBuilder("tok_abc", state=DeliveryState.CANCELLED.value)
        assert builder.state == DeliveryState.CANCELLED.value
