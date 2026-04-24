"""Delivery Context — CORE-DELIVERY-CONTEXT-306-A

Bounded context envelope: add read-only `context` object to delivery status/proof.
context: { zone?, surface?, prompt_label? }
Derived from stored metadata only. Missing = explicit null fields, no crash.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.delivery_interactive import (
    delivery_bp,
    _set_delivery_intent_store_for_testing,
    DeliveryState,
)
from copilot_core.api.v1.delivery_intent_store import DeliveryIntentStore
# Import observability to trigger /proof route registration on delivery_bp
import copilot_core.api.v1.observability  # noqa: F401
from unittest.mock import patch
import copilot_core.api.security as security


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(delivery_bp)
    return app


def _with_auth():
    return patch('copilot_core.api.security.validate_token', return_value=True)


def _make_token() -> str:
    return str(uuid.uuid4())


# ── Context envelope contract tests ─────────────────────────────────────────────

class TestDeliveryContextEnvelope:
    """context is exposed on acknowledge response when metadata contains context fields."""

    def test_acknowledge_with_context_returns_context(self):
        """When metadata has zone/surface/prompt_label, response includes context."""
        app = _make_app()
        token = _make_token()
        ctx = {"zone": "living_room", "surface": "Echo Show", "prompt_label": "Lüftung?"}
        with _with_auth():
            d = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge", "metadata": {"context": ctx}}
            ).get_json()
            assert "context" in d, f"missing context in {d}"
            assert d["context"]["zone"] == "living_room"
            assert d["context"]["surface"] == "Echo Show"
            assert d["context"]["prompt_label"] == "Lüftung?"

    def test_acknowledge_without_context_returns_null_fields(self):
        """When metadata has no context, response has explicit null context fields."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            d = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"}
            ).get_json()
            assert "context" in d
            assert d["context"]["zone"] is None
            assert d["context"]["surface"] is None
            assert d["context"]["prompt_label"] is None

    def test_acknowledge_with_partial_context(self):
        """Partial context fields: present ones preserved, missing ones null."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            d = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge",
                      "metadata": {"context": {"zone": "kitchen"}}}
            ).get_json()
            assert d["context"]["zone"] == "kitchen"
            assert d["context"]["surface"] is None
            assert d["context"]["prompt_label"] is None

    def test_cancel_preserves_context(self):
        """Cancel does not wipe context — it persists in state."""
        app = _make_app()
        token = _make_token()
        ctx = {"zone": "bedroom", "surface": "Nest Hub", "prompt_label": "Guten Morgen"}
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                   json={"delivery_token": token, "action": "acknowledge",
                         "metadata": {"context": ctx}})
            d = c.post("/api/v1/delivery/acknowledge",
                       json={"delivery_token": token, "action": "cancel"}).get_json()
            assert d["context"]["zone"] == "bedroom"
            assert d["context"]["surface"] == "Nest Hub"
            assert d["context"]["prompt_label"] == "Guten Morgen"


class TestDeliveryStatusContext:
    """GET /status includes context when available."""

    def test_status_with_context(self):
        app = _make_app()
        token = _make_token()
        ctx = {"zone": "office", "surface": "Fire Tablet", "prompt_label": "Meeting?"}
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                   json={"delivery_token": token, "action": "acknowledge",
                         "metadata": {"context": ctx}})
            d = c.get(f"/api/v1/delivery/{token}/status").get_json()
            assert "context" in d
            assert d["context"]["zone"] == "office"
            assert d["context"]["surface"] == "Fire Tablet"
            assert d["context"]["prompt_label"] == "Meeting?"

    def test_status_without_context(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                   json={"delivery_token": token, "action": "acknowledge"})
            d = c.get(f"/api/v1/delivery/{token}/status").get_json()
            assert "context" in d
            assert d["context"]["zone"] is None
            assert d["context"]["surface"] is None
            assert d["context"]["prompt_label"] is None


class TestDeliveryProofContext:
    """GET /proof includes context when available."""

    def test_proof_with_context(self):
        app = _make_app()
        token = _make_token()
        ctx = {"zone": "garage", "surface": "Smart Display", "prompt_label": "Tür offen?"}
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                   json={"delivery_token": token, "action": "acknowledge",
                         "metadata": {"context": ctx}})
            d = c.get(f"/api/v1/delivery/{token}/proof").get_json()
            assert "context" in d
            assert d["context"]["zone"] == "garage"
            assert d["context"]["surface"] == "Smart Display"
            assert d["context"]["prompt_label"] == "Tür offen?"

    def test_proof_without_context(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                   json={"delivery_token": token, "action": "acknowledge"})
            d = c.get(f"/api/v1/delivery/{token}/proof").get_json()
            assert "context" in d
            assert d["context"]["zone"] is None


class TestContextNonGoals:
    """Verify context does not open new endpoints or widen semantics."""

    def test_no_new_endpoint_added(self):
        """No /context endpoint exists."""
        app = _make_app()
        with _with_auth():
            r = app.test_client().get("/api/v1/delivery/some-token/context")
            # Should 404, not 200
            assert r.status_code == 404, f"context endpoint should not exist, got {r.status_code}"

    def test_context_is_read_only(self):
        """Context cannot be set via status or proof endpoint."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                   json={"delivery_token": token, "action": "acknowledge"})
            # PUT/PATCH to status should 404 or be rejected
            r = c.put(f"/api/v1/delivery/{token}/status",
                      json={"context": {"zone": "hacked"}})
            assert r.status_code in (404, 405), "context must not be settable via status"
