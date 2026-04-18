"""Contract tests for API security scope and admin gating."""
from __future__ import annotations

from flask import Flask, g, jsonify


app = Flask(__name__)


def _unwrap_status(response) -> int:
    if isinstance(response, tuple):
        return response[1]
    return response.status_code


class TestRequireTokenScopes:
    def test_require_token_scope_rejects_missing_scope(self, monkeypatch):
        from copilot_core.api import security

        @security.require_token(scopes=("read",))
        def handler():
            return jsonify({"ok": True})

        monkeypatch.setattr(security, "validate_token", lambda request: True)

        with app.test_request_context("/"):
            g.token_valid = True
            g.token_scopes = {"write"}
            response = handler()

        assert _unwrap_status(response) == 403

    def test_require_token_scope_accepts_matching_scope(self, monkeypatch):
        from copilot_core.api import security

        @security.require_token(scopes=("read",))
        def handler():
            return jsonify({"ok": True})

        monkeypatch.setattr(security, "validate_token", lambda request: True)

        with app.test_request_context("/"):
            g.token_valid = True
            g.token_scopes = {"read", "write"}
            response = handler()

        assert _unwrap_status(response) == 200


class TestRequireScope:
    def test_require_scope_needs_authenticated_token_first(self):
        from copilot_core.api import security

        @security.require_scope("admin")
        def handler():
            return jsonify({"ok": True})

        with app.test_request_context("/"):
            g.token_valid = False
            g.token_scopes = {"admin"}
            response = handler()

        assert _unwrap_status(response) == 401

    def test_require_scope_rejects_missing_scope(self):
        from copilot_core.api import security

        @security.require_scope("admin")
        def handler():
            return jsonify({"ok": True})

        with app.test_request_context("/"):
            g.token_valid = True
            g.token_scopes = {"read"}
            response = handler()

        assert _unwrap_status(response) == 403


class TestRequireAdminToken:
    def test_require_admin_token_requires_admin_scope_when_auth_enabled(self, monkeypatch):
        from copilot_core.api import security

        monkeypatch.setattr(security, "get_auth_token", lambda: "secret-token")
        monkeypatch.setattr(security, "is_auth_required", lambda: True)

        with app.test_request_context("/", headers={"X-Auth-Token": "secret-token"}):
            g.token_valid = True
            g.token_scopes = {"read"}
            assert security.require_admin_token(security.request) is False

        with app.test_request_context("/", headers={"X-Auth-Token": "secret-token"}):
            g.token_valid = True
            g.token_scopes = {"admin"}
            assert security.require_admin_token(security.request) is True

    def test_require_admin_token_allows_valid_token_when_auth_disabled(self, monkeypatch):
        from copilot_core.api import security

        monkeypatch.setattr(security, "get_auth_token", lambda: "secret-token")
        monkeypatch.setattr(security, "is_auth_required", lambda: False)

        with app.test_request_context("/", headers={"Authorization": "Bearer secret-token"}):
            g.token_valid = True
            g.token_scopes = set()
            assert security.require_admin_token(security.request) is True

class TestTokenAgeEnforcement:
    """GAP-5 contract tests: auto-token age enforcement via _get_token_age()."""

    def test_get_token_age_returns_none_for_nonexistent_file(self, monkeypatch):
        from copilot_core.api import security

        monkeypatch.setattr(security, "AUTO_TOKEN_PATH", "/nonexistent/path/token")
        age = security._get_token_age()
        assert age is None

    def test_get_token_age_returns_age_for_valid_file(self, monkeypatch, tmp_path):
        from copilot_core.api import security
        import time

        token_file = tmp_path / "token"
        recent = int(time.time()) - (30 * 86400)
        token_file.write_text("test-token\n" + str(recent) + "\n")
        monkeypatch.setattr(security, "AUTO_TOKEN_PATH", str(token_file))

        age = security._get_token_age()
        assert age is not None
        assert 20 * 86400 < age < 40 * 86400, f"Expected ~30 days, got {age}"

    def test_get_token_age_returns_none_for_single_line_file(self, monkeypatch, tmp_path):
        from copilot_core.api import security

        token_file = tmp_path / "token"
        token_file.write_text("only-token-no-age\n")
        monkeypatch.setattr(security, "AUTO_TOKEN_PATH", str(token_file))

        age = security._get_token_age()
        assert age is None

    def test_get_token_age_returns_none_for_empty_file(self, monkeypatch, tmp_path):
        from copilot_core.api import security

        token_file = tmp_path / "token"
        token_file.write_text("")
        monkeypatch.setattr(security, "AUTO_TOKEN_PATH", str(token_file))

        age = security._get_token_age()
        assert age is None


class TestAuthRequiredCaching:
    """GAP-3 contract tests: is_auth_required() TTL cache via monotonic time."""

    def test_is_auth_required_respects_ttl_cache(self, monkeypatch, tmp_path):
        from copilot_core.api import security
        import time

        # Fresh options file
        opts_file = tmp_path / "options.json"
        opts_file.write_text("{}")
        monkeypatch.setattr(security, "OPTIONS_PATH", str(opts_file))

        # Reset cache (result=True, timestamp=0 means "expired")
        security._auth_required_cache = (True, 0.0)

        # First call: should compute (cache miss)
        r1 = security.is_auth_required()

        # Immediately second call: within TTL, should be cached
        r2 = security.is_auth_required()

        # Verify result is consistent
        assert r1 is r2 is True
        # Verify we got the cached result (not a new computation)
        # Cache should still be populated from first call
        cached_result, cached_at = security._auth_required_cache
        assert cached_result is True
        # Cache should not have been recomputed within TTL
        now = time.monotonic()
        assert now - cached_at < security._AUTH_CACHE_TTL

