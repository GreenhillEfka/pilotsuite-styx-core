"""Delivery Interactive API — CORE-HARDEN-217 (303-A acknowledgment seam)

Bounded interaction contract:
  POST /api/v1/delivery/acknowledge
    body: { delivery_token: str, action: "acknowledge" | "cancel", metadata?: dict }
    response: { ok: bool, delivery_token: str, state: "acknowledged" | "cancelled", timestamp: str }

  GET /api/v1/delivery/{delivery_token}/status
    response: { delivery_token: str, state: str, created_at: str, expires_at: str }

Semantics:
  - delivery_token: opaque correlation token, UUID4
  - states: pending | acknowledged | cancelled | expired
  - expiry: 5 minutes from creation
  - cancel: user-initiated stop before expiry
  - idempotent: re-acknowledge returns same state
"""
from __future__ import annotations

import sys
import os
import uuid
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask, jsonify, request
from copilot_core.api.v1.delivery_interactive import (
    delivery_bp,
    _store,
    _lock,
    _TTL_SECONDS,
    DeliveryState,
)
import copilot_core.api.security as security
def _make_app():
    app = Flask(__name__)
    app.register_blueprint(delivery_bp)
    return app


from unittest.mock import patch


def _with_auth():
    return patch('copilot_core.api.security.validate_token', return_value=True)


def _make_token() -> str:
    return str(uuid.uuid4())


# ── Acknowledgment seam contract tests ────────────────────────────────────────

class TestDeliveryCreate:
    """POST /api/v1/delivery/acknowledge — create or update a delivery token."""

    def test_acknowledge_returns_200(self):
        app = _make_app()
        with _with_auth():
            r = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": _make_token(), "action": "acknowledge"}
            )
            assert r.status_code == 200, f"got {r.status_code}: {r.get_json()}"

    def test_acknowledge_returns_delivery_token(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            d = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"}
            ).get_json()
            assert d["delivery_token"] == token

    def test_acknowledge_returns_acknowledged_state(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            d = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"}
            ).get_json()
            assert d["state"] == DeliveryState.ACKNOWLEDGED.value

    def test_acknowledge_requires_auth(self):
        r = _make_app().test_client().post(
            "/api/v1/delivery/acknowledge",
            json={"delivery_token": _make_token(), "action": "acknowledge"}
        )
        assert r.status_code in (401, 403)

    def test_cancel_returns_cancelled_state(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            d = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "cancel"}
            ).get_json()
            assert d["state"] == DeliveryState.CANCELLED.value

    def test_cancel_requires_auth(self):
        r = _make_app().test_client().post(
            "/api/v1/delivery/acknowledge",
            json={"delivery_token": _make_token(), "action": "cancel"}
        )
        assert r.status_code in (401, 403)

    def test_missing_delivery_token_returns_400(self):
        app = _make_app()
        with _with_auth():
            r = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"action": "acknowledge"}
            )
            assert r.status_code == 400

    def test_missing_action_returns_400(self):
        app = _make_app()
        with _with_auth():
            r = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": _make_token()}
            )
            assert r.status_code == 400

    def test_unknown_action_returns_400(self):
        app = _make_app()
        with _with_auth():
            r = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": _make_token(), "action": "maybe"}
            )
            assert r.status_code == 400

    def test_idempotent_acknowledge_returns_same_state(self):
        """Re-acknowledge is idempotent — returns existing state."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            d1 = c.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"}
            ).get_json()
            d2 = c.post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"}
            ).get_json()
            assert d1["state"] == d2["state"] == DeliveryState.ACKNOWLEDGED.value

    def test_acknowledge_with_metadata_persists(self):
        app = _make_app()
        token = _make_token()
        meta = {"zone": "living_room", "person": "alice"}
        with _with_auth():
            d = app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge", "metadata": meta}
            ).get_json()
            assert d.get("metadata") == meta

    def test_cancel_overrides_pending(self):
        """Cancel after pending → cancelled."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            c.post("/api/v1/delivery/acknowledge",
                   json={"delivery_token": token, "action": "acknowledge"})
            d = c.post("/api/v1/delivery/acknowledge",
                       json={"delivery_token": token, "action": "cancel"}).get_json()
            assert d["state"] == DeliveryState.CANCELLED.value


class TestDeliveryStatus:
    """GET /api/v1/delivery/{delivery_token}/status."""

    def test_status_returns_200(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            r = app.test_client().get(f"/api/v1/delivery/{token}/status")
            assert r.status_code == 200, f"got {r.status_code}"

    def test_status_returns_token_and_state(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            # First create the token via acknowledge
            app.test_client().post(
                "/api/v1/delivery/acknowledge",
                json={"delivery_token": token, "action": "acknowledge"}
            )
            d = app.test_client().get(f"/api/v1/delivery/{token}/status").get_json()
            assert d["delivery_token"] == token
            assert "state" in d

    def test_status_requires_auth(self):
        token = _make_token()
        r = _make_app().test_client().get(f"/api/v1/delivery/{token}/status")
        assert r.status_code in (401, 403)

    def test_unknown_token_returns_pending(self):
        """A token never seen returns pending (zero-state)."""
        app = _make_app()
        token = _make_token()
        with _with_auth():
            d = app.test_client().get(f"/api/v1/delivery/{token}/status").get_json()
            assert d["state"] == DeliveryState.PENDING.value


class TestDeliverySmoke:
    """Smoke test: full acknowledge → status → cancel lifecycle."""

    def test_full_lifecycle(self):
        app = _make_app()
        token = _make_token()
        with _with_auth():
            c = app.test_client()
            # acknowledge
            r1 = c.post("/api/v1/delivery/acknowledge",
                         json={"delivery_token": token, "action": "acknowledge"})
            assert r1.status_code == 200
            # check status
            r2 = c.get(f"/api/v1/delivery/{token}/status")
            assert r2.status_code == 200
            d2 = r2.get_json()
            assert d2["state"] == DeliveryState.ACKNOWLEDGED.value
            # cancel
            r3 = c.post("/api/v1/delivery/acknowledge",
                        json={"delivery_token": token, "action": "cancel"})
            assert r3.status_code == 200
            d3 = r3.get_json()
            assert d3["state"] == DeliveryState.CANCELLED.value
            # status reflects cancelled
            d4 = c.get(f"/api/v1/delivery/{token}/status").get_json()
            assert d4["state"] == DeliveryState.CANCELLED.value
