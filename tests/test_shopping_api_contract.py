"""Shopping & Reminders API Contract Tests — CORE-HARDEN-214"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.shopping import shopping_bp
import copilot_core.api.security as security


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(shopping_bp)
    return app


def _with_auth():
    return patch.object(security, 'validate_token', return_value=True)


# ── Mock DB row factory ─────────────────────────────────────────────────

def _row(**fields):
    return fields


# ── Mock connection factory ─────────────────────────────────────────────

def _make_conn(rows=None, rowcount=1):
    """Mock sqlite connection that returns canned rows."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = rowcount
    mock_cursor.fetchall.return_value = rows or []
    mock_cursor.fetchone.return_value = rows[0] if rows else None
    mock_conn.execute.return_value = mock_cursor
    mock_conn.commit.return_value = None
    return mock_conn


class TestListShopping:
    """GET /api/v1/shopping"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rows=[_row(id="s1", name="Milch", completed="0")])):
                client = app.test_client()
                r = client.get("/api/v1/shopping")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_returns_items_array(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rows=[_row(id="s1", name="Milch", completed="0")])):
                client = app.test_client()
                r = client.get("/api/v1/shopping")
                d = r.get_json()
                assert "items" in d
                assert "count" in d

    def test_get_filter_incomplete(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rows=[])):
                client = app.test_client()
                r = client.get("/api/v1/shopping?completed=0")
                assert r.status_code == 200

    def test_get_filter_complete(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rows=[])):
                client = app.test_client()
                r = client.get("/api/v1/shopping?completed=1")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/shopping")
        assert r.status_code in (401, 403)


class TestAddShopping:
    """POST /api/v1/shopping"""

    def test_post_single_item_returns_201(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn()):
                client = app.test_client()
                r = client.post("/api/v1/shopping", json={"name": "Brot"})
                assert r.status_code == 201, f"expected 201, got {r.status_code}"

    def test_post_single_item_returns_success(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn()):
                client = app.test_client()
                r = client.post("/api/v1/shopping", json={"name": "Brot"})
                d = r.get_json()
                assert d.get("success") is True
                assert "added" in d

    def test_post_multiple_items_returns_201(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn()):
                client = app.test_client()
                r = client.post("/api/v1/shopping", json={
                    "items": [{"name": "Milch"}, {"name": "Brot"}]
                })
                assert r.status_code == 201

    def test_post_empty_body_returns_400(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn()):
                client = app.test_client()
                r = client.post("/api/v1/shopping", json={})
                assert r.status_code == 400

    def test_post_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/shopping", json={"name": "Brot"})
        assert r.status_code in (401, 403)


class TestCompleteShopping:
    """POST /api/v1/shopping/<item_id>/complete"""

    def test_post_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=1)):
                client = app.test_client()
                r = client.post("/api/v1/shopping/s123/complete")
                assert r.status_code == 200

    def test_post_returns_success(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=1)):
                client = app.test_client()
                r = client.post("/api/v1/shopping/s123/complete")
                d = r.get_json()
                assert d.get("success") is True

    def test_post_not_found_returns_404(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=0)):
                client = app.test_client()
                r = client.post("/api/v1/shopping/nonexistent/complete")
                assert r.status_code == 404

    def test_post_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/shopping/s123/complete")
        assert r.status_code in (401, 403)


class TestDeleteShopping:
    """DELETE /api/v1/shopping/<item_id>"""

    def test_delete_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=1)):
                client = app.test_client()
                r = client.delete("/api/v1/shopping/s123")
                assert r.status_code == 200

    def test_delete_not_found_returns_404(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=0)):
                client = app.test_client()
                r = client.delete("/api/v1/shopping/nonexistent")
                assert r.status_code == 404

    def test_delete_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.delete("/api/v1/shopping/s123")
        assert r.status_code in (401, 403)


class TestClearCompletedShopping:
    """POST /api/v1/shopping/clear-completed"""

    def test_clear_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn()):
                client = app.test_client()
                r = client.post("/api/v1/shopping/clear-completed")
                assert r.status_code == 200

    def test_clear_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/shopping/clear-completed")
        assert r.status_code in (401, 403)


class TestListReminders:
    """GET /api/v1/reminders"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rows=[_row(id="r1", title="Test", completed="0")])):
                client = app.test_client()
                r = client.get("/api/v1/reminders")
                assert r.status_code == 200

    def test_get_returns_reminders_array(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rows=[_row(id="r1", title="Test", completed="0")])):
                client = app.test_client()
                r = client.get("/api/v1/reminders")
                d = r.get_json()
                assert "reminders" in d
                assert "count" in d

    def test_get_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/reminders")
        assert r.status_code in (401, 403)


class TestAddReminder:
    """POST /api/v1/reminders"""

    def test_post_returns_201(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn()):
                client = app.test_client()
                r = client.post("/api/v1/reminders", json={"title": "Neue Erinnerung"})
                assert r.status_code == 201

    def test_post_returns_success(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn()):
                client = app.test_client()
                r = client.post("/api/v1/reminders", json={"title": "Neue Erinnerung"})
                d = r.get_json()
                assert d.get("success") is True

    def test_post_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/reminders", json={"title": "Neue Erinnerung"})
        assert r.status_code in (401, 403)


class TestCompleteReminder:
    """POST /api/v1/reminders/<rem_id>/complete"""

    def test_post_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=1)):
                client = app.test_client()
                r = client.post("/api/v1/reminders/r123/complete")
                assert r.status_code == 200

    def test_post_not_found_returns_404(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=0)):
                client = app.test_client()
                r = client.post("/api/v1/reminders/nonexistent/complete")
                assert r.status_code == 404

    def test_post_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/reminders/r123/complete")
        assert r.status_code in (401, 403)


class TestSnoozeReminder:
    """POST /api/v1/reminders/<rem_id>/snooze"""

    def test_post_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=1)):
                client = app.test_client()
                r = client.post("/api/v1/reminders/r123/snooze", json={"minutes": 30})
                assert r.status_code == 200

    def test_post_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/reminders/r123/snooze", json={"minutes": 30})
        assert r.status_code in (401, 403)


class TestDeleteReminder:
    """DELETE /api/v1/reminders/<rem_id>"""

    def test_delete_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=1)):
                client = app.test_client()
                r = client.delete("/api/v1/reminders/r123")
                assert r.status_code == 200

    def test_delete_not_found_returns_404(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.shopping._get_conn",
                       return_value=_make_conn(rowcount=0)):
                client = app.test_client()
                r = client.delete("/api/v1/reminders/nonexistent")
                assert r.status_code == 404

    def test_delete_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.delete("/api/v1/reminders/r123")
        assert r.status_code in (401, 403)
