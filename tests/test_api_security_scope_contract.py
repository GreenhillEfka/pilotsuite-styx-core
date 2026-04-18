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
            g.token_scopes = {"read"}
            assert security.require_admin_token(security.flask_request) is False

        with app.test_request_context("/", headers={"X-Auth-Token": "secret-token"}):
            g.token_scopes = {"admin"}
            assert security.require_admin_token(security.flask_request) is True

    def test_require_admin_token_allows_valid_token_when_auth_disabled(self, monkeypatch):
        from copilot_core.api import security

        monkeypatch.setattr(security, "get_auth_token", lambda: "secret-token")
        monkeypatch.setattr(security, "is_auth_required", lambda: False)

        with app.test_request_context("/", headers={"Authorization": "Bearer secret-token"}):
            g.token_scopes = set()
            assert security.require_admin_token(security.flask_request) is True
