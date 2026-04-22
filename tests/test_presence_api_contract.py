"""Presence API Contract Tests — CORE-HARDEN-212"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.presence import presence_bp
from unittest.mock import patch


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(presence_bp)
    return app


def _with_auth():
    return patch("copilot_core.api.security.validate_token", return_value=True)


def _auth_headers():
    return {"Authorization": "Bearer test-token"}


# ─────────────────────────────────────────────────────────────────────────────
# Status — GET /api/v1/presence/status
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceStatus:
    """GET /api/v1/presence/status — current presence map."""

    def test_get_status_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/status", headers=_auth_headers())
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_status_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/status", headers=_auth_headers())
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_get_status_returns_total_tracked(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/status", headers=_auth_headers())
            data = r.get_json()
            assert "total_tracked" in data, f"'total_tracked' missing: {data}"

    def test_get_status_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/presence/status")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Update — POST /api/v1/presence/update
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceUpdate:
    """POST /api/v1/presence/update — receive presence update."""

    def test_post_update_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/update",
                headers=_auth_headers(),
                json={"persons": [{"person_id": "alice", "state": "home", "source": "ha"}]},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_update_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/update",
                headers=_auth_headers(),
                json={"persons": [{"person_id": "alice", "state": "home", "source": "ha"}]},
            )
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_update_missing_persons_returns_400(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/update",
                headers=_auth_headers(),
                json={"state": "home"},
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_update_invalid_source_defaults_to_ha(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/update",
                headers=_auth_headers(),
                json={"persons": [{"person_id": "alice", "state": "home", "source": "invalid_source"}]},
            )
            # source validation: falls back to 'ha', so 200
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_update_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post(
            "/api/v1/presence/update",
            json={"persons": [{"person_id": "alice", "state": "home", "source": "ha"}]},
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Hold — POST /api/v1/presence/hold
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceHold:
    """POST /api/v1/presence/hold — set manual presence hold."""

    def test_post_hold_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/hold",
                headers=_auth_headers(),
                json={"person_id": "alice", "hold": "force_on"},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_hold_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/hold",
                headers=_auth_headers(),
                json={"person_id": "alice", "hold": "force_on"},
            )
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_hold_missing_person_id_returns_400(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/hold",
                headers=_auth_headers(),
                json={"hold": "force_on"},
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_hold_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post(
            "/api/v1/presence/hold",
            json={"person_id": "alice", "hold": "force_on"},
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Hold clear — DELETE /api/v1/presence/hold
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceHoldClear:
    """DELETE /api/v1/presence/hold — clear manual presence hold (query param: person_id)."""

    def test_delete_hold_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.delete(
                "/api/v1/presence/hold?person_id=alice",
                headers=_auth_headers(),
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_delete_hold_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.delete(
                "/api/v1/presence/hold?person_id=alice",
                headers=_auth_headers(),
            )
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_delete_hold_missing_person_id_returns_400(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.delete(
                "/api/v1/presence/hold",
                headers=_auth_headers(),
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_delete_hold_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.delete("/api/v1/presence/hold?person_id=alice")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Zone presence hold — POST /api/v1/presence/zone/presence/<zone_id>/hold
# ─────────────────────────────────────────────────────────────────────────────

class TestZonePresenceHold:
    """POST /api/v1/presence/zone/presence/<zone_id>/hold."""

    def test_post_zone_hold_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/zone/presence/wohnzimmer/hold",
                headers=_auth_headers(),
                json={"hold": "force_on"},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_zone_hold_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/zone/presence/wohnzimmer/hold",
                headers=_auth_headers(),
                json={"hold": "force_on"},
            )
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_zone_hold_invalid_hold_value_returns_400(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/zone/presence/wohnzimmer/hold",
                headers=_auth_headers(),
                json={"hold": "invalid_value"},
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_post_zone_hold_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post(
            "/api/v1/presence/zone/presence/wohnzimmer/hold",
            json={"hold": "force_on"},
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Zone presence state — POST /api/v1/presence/zone/presence/<zone_id>/state
# ─────────────────────────────────────────────────────────────────────────────

class TestZonePresenceState:
    """POST /api/v1/presence/zone/presence/<zone_id>/state."""

    def test_post_zone_state_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/zone/presence/wohnzimmer/state",
                headers=_auth_headers(),
                json={"state": "home", "source": "motion"},
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_zone_state_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/zone/presence/wohnzimmer/state",
                headers=_auth_headers(),
                json={"state": "home", "source": "motion"},
            )
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_zone_state_missing_state_uses_default(self):
        """Missing 'state' body field defaults to 'unknown' and returns 200."""
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post(
                "/api/v1/presence/zone/presence/wohnzimmer/state",
                headers=_auth_headers(),
                json={},
            )
            # state field defaults to 'unknown' — no 400, returns 200
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_zone_state_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post(
            "/api/v1/presence/zone/presence/wohnzimmer/state",
            json={"state": "home"},
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Sources — GET /api/v1/presence/sources
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceSources:
    """GET /api/v1/presence/sources — get sources for a person (query param: person_id)."""

    def test_get_sources_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/sources?person_id=alice", headers=_auth_headers())
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_sources_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/sources?person_id=alice", headers=_auth_headers())
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_get_sources_missing_person_id_returns_400(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/sources", headers=_auth_headers())
            assert r.status_code == 400, f"expected 400, got {r.status_code} / {r.get_json()}"

    def test_get_sources_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/presence/sources?person_id=alice")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# History — GET /api/v1/presence/history
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceHistory:
    """GET /api/v1/presence/history — recent presence events."""

    def test_get_history_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/history", headers=_auth_headers())
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_get_history_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.get("/api/v1/presence/history", headers=_auth_headers())
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_get_history_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/presence/history")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# Check timeouts — POST /api/v1/presence/check_timeouts
# ─────────────────────────────────────────────────────────────────────────────

class TestPresenceCheckTimeouts:
    """POST /api/v1/presence/check_timeouts — trigger timeout check."""

    def test_post_check_timeouts_returns_200(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post("/api/v1/presence/check_timeouts", headers=_auth_headers(), json={})
            assert r.status_code == 200, f"expected 200, got {r.status_code} / {r.get_json()}"

    def test_post_check_timeouts_returns_ok_flag(self):
        app = _make_app()
        with _with_auth():
            client = app.test_client()
            r = client.post("/api/v1/presence/check_timeouts", headers=_auth_headers(), json={})
            data = r.get_json()
            assert data.get("ok") is True, f"expected ok=True, got {data}"

    def test_post_check_timeouts_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/presence/check_timeouts", json={})
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"
