"""Cache Control API Contract Tests — CORE-HARDEN-213"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.cache_control import cache_control_bp
import copilot_core.api.security as security


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(cache_control_bp, url_prefix="/api/v1/cache")
    return app


def _with_auth():
    return patch.object(security, 'validate_token', return_value=True)


# ── Fresh mock factories ──────────────────────────────────────────────

def _make_redis_client(connected=True):
    mock = MagicMock()
    mock.is_connected = connected
    mock.host = "localhost"
    mock.port = 6379
    return mock


def _make_cache():
    async def _inv_all():
        return None
    async def _inv(key):
        return True
    async def _inv_pattern(p):
        return 5
    async def _inv_entities():
        return 10
    async def _inv_states():
        return 3
    async def _get_stats():
        return {"hits": 100, "misses": 20, "size": 50}
    mock = MagicMock()
    mock.invalidate_all = _inv_all
    mock.invalidate = _inv
    mock.invalidate_pattern = _inv_pattern
    mock.invalidate_entities = _inv_entities
    mock.invalidate_states = _inv_states
    mock.get_stats = _get_stats
    return mock


class TestCacheStatus:
    """GET /api/v1/cache/status"""

    def test_get_status_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_redis_client",
                       return_value=_make_redis_client(connected=True)):
                client = app.test_client()
                r = client.get("/api/v1/cache/status")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_status_returns_success_flag(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_redis_client",
                       return_value=_make_redis_client(connected=True)):
                client = app.test_client()
                r = client.get("/api/v1/cache/status")
                data = r.get_json()
                assert data.get("success") is True, f"expected success=True, got {data}"

    def test_get_status_returns_connected_data(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_redis_client",
                       return_value=_make_redis_client(connected=True)):
                client = app.test_client()
                r = client.get("/api/v1/cache/status")
                d = r.get_json().get("data", {})
                assert "connected" in d
                assert "host" in d
                assert "port" in d
                assert "using_fallback" in d

    def test_get_status_fallback_connected_false(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_redis_client",
                       return_value=_make_redis_client(connected=False)):
                client = app.test_client()
                r = client.get("/api/v1/cache/status")
                d = r.get_json().get("data", {})
                assert d.get("using_fallback") is True
                assert d.get("connected") is False

    def test_get_status_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/cache/status")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


class TestCacheInvalidate:
    """POST /api/v1/cache/invalidate"""

    def test_post_invalidate_all_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.post("/api/v1/cache/invalidate", json={"all": True})
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_invalidate_all_returns_message(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.post("/api/v1/cache/invalidate", json={"all": True})
                d = r.get_json().get("data", {})
                assert d.get("invalidated") == "all"

    def test_post_invalidate_by_key_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.post("/api/v1/cache/invalidate", json={"key": "entity:kitchen"})
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_post_invalidate_by_pattern_returns_200_with_count(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.post("/api/v1/cache/invalidate",
                                json={"pattern": "entity:kitchen:*"})
                assert r.status_code == 200
                d = r.get_json().get("data", {})
                assert d.get("pattern") == "entity:kitchen:*"
                assert "invalidated_count" in d

    def test_post_invalidate_default_returns_entity_and_state_counts(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.post("/api/v1/cache/invalidate", json={})
                assert r.status_code == 200, f"expected 200, got {r.status_code}"
                d = r.get_json().get("data", {})
                assert "invalidated_entities" in d
                assert "invalidated_states" in d
                assert d.get("total") == 13

    def test_post_invalidate_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.post("/api/v1/cache/invalidate", json={"all": True})
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


class TestCacheStats:
    """GET /api/v1/cache/stats"""

    def test_get_stats_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.get("/api/v1/cache/stats")
                assert r.status_code == 200, f"expected 200, got {r.status_code}"

    def test_get_stats_returns_success_flag(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.get("/api/v1/cache/stats")
                data = r.get_json()
                assert data.get("success") is True, f"expected success=True, got {data}"

    def test_get_stats_returns_data_object(self):
        app = _make_app()
        with _with_auth():
            with patch("copilot_core.api.v1.cache_control.get_api_cache",
                       return_value=_make_cache()):
                client = app.test_client()
                r = client.get("/api/v1/cache/stats")
                d = r.get_json().get("data", {})
                assert "hits" in d
                assert "misses" in d
                assert "size" in d

    def test_get_stats_requires_auth(self):
        app = _make_app()
        client = app.test_client()
        r = client.get("/api/v1/cache/stats")
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"
