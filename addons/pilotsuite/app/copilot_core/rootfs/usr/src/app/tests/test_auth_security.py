"""Comprehensive authentication security tests.

Tests verify that:
1. All protected endpoints return 401 when no token is provided
2. Valid tokens allow access
3. Invalid tokens are rejected
4. Token formats (X-Auth-Token and Bearer) are both accepted
5. Allowlisted paths bypass auth
6. Empty token config allows all requests (first-run experience)
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

try:
    from copilot_core.app import create_app
    from copilot_core.api.security import validate_token, get_auth_token, is_auth_required
    _FLASK_AVAILABLE = True
except ModuleNotFoundError:
    _FLASK_AVAILABLE = False
    create_app = None


def _make_app(token: str = "test-secret", auth_required: bool = True):
    """Create a test Flask app with known auth config."""
    app = create_app()
    app.config["TESTING"] = True
    # Override auth via environment (highest priority)
    return app


class TestSecurityModule(unittest.TestCase):
    """Unit tests for security.py functions."""

    def test_validate_token_with_x_auth_token_header(self):
        """validate_token accepts X-Auth-Token header."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        app = create_app()
        with app.test_request_context(
            headers={"X-Auth-Token": "mytoken"},
            environ_base={"COPILOT_AUTH_TOKEN": "mytoken"}
        ):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value="mytoken"), \
                 patch("copilot_core.api.security.is_auth_required", return_value=True):
                self.assertTrue(validate_token(request))

    def test_validate_token_with_bearer_token(self):
        """validate_token accepts Authorization: Bearer header."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        app = create_app()
        with app.test_request_context(
            headers={"Authorization": "Bearer mytoken"},
        ):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value="mytoken"), \
                 patch("copilot_core.api.security.is_auth_required", return_value=True):
                self.assertTrue(validate_token(request))

    def test_validate_token_rejects_wrong_token(self):
        """validate_token rejects incorrect token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        app = create_app()
        with app.test_request_context(
            headers={"X-Auth-Token": "wrong-token"},
        ):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value="correct-token"), \
                 patch("copilot_core.api.security.is_auth_required", return_value=True):
                self.assertFalse(validate_token(request))

    def test_validate_token_allows_when_no_token_configured(self):
        """Empty auth token = allow all (first-run experience)."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        app = create_app()
        with app.test_request_context():
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value=""), \
                 patch("copilot_core.api.security.is_auth_required", return_value=True):
                self.assertTrue(validate_token(request))

    def test_validate_token_allows_when_auth_disabled(self):
        """Auth disabled = allow all requests."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        app = create_app()
        with app.test_request_context():
            from flask import request
            with patch("copilot_core.api.security.is_auth_required", return_value=False):
                self.assertTrue(validate_token(request))


class TestAllowlistedPaths(unittest.TestCase):
    """Test that allowlisted paths bypass authentication."""

    def setUp(self):
        if not _FLASK_AVAILABLE:
            return
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def _with_token_required(self):
        """Context: auth required with configured token."""
        return patch.multiple(
            "copilot_core.api.security",
            get_auth_token=lambda *a, **kw: "secret",
            is_auth_required=lambda *a, **kw: True,
        )

    def test_health_no_auth_needed(self):
        """GET /health should be accessible without token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        with patch("copilot_core.api.security.get_auth_token", return_value="secret"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)

    def test_root_no_auth_needed(self):
        """GET / should be accessible without token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        with patch("copilot_core.api.security.get_auth_token", return_value="secret"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_version_no_auth_needed(self):
        """GET /version should be accessible without token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        with patch("copilot_core.api.security.get_auth_token", return_value="secret"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get("/version")
        self.assertEqual(r.status_code, 200)

    def test_api_status_no_auth_needed(self):
        """GET /api/v1/status should be accessible without token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        with patch("copilot_core.api.security.get_auth_token", return_value="secret"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get("/api/v1/status")
        self.assertEqual(r.status_code, 200)


class TestProtectedEndpoints(unittest.TestCase):
    """Test that protected endpoints enforce authentication."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/v1/events"),
        ("GET", "/api/v1/events/stats"),
        ("GET", "/graph/state"),
        ("GET", "/graph/stats"),
        ("GET", "/graph/patterns"),
        ("GET", "/candidates"),
        ("GET", "/mood/state"),
        ("GET", "/neurons"),
        ("GET", "/vector/stats"),
        ("GET", "/vector/vectors"),
        ("GET", "/user/all"),
        ("GET", "/search"),
        ("GET", "/notifications"),
        ("GET", "/weather/"),
        ("GET", "/habitus/status"),
        ("GET", "/habitus/health"),
        ("GET", "/voice/context"),
        ("GET", "/dashboard/brain-summary"),
        ("GET", "/hints"),
        ("GET", "/debug"),
        ("GET", "/api/v1/tag-system/tags"),
        ("GET", "/api/v1/tag-system/assignments"),
    ]

    def setUp(self):
        if not _FLASK_AVAILABLE:
            return
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_no_token_returns_401(self):
        """All protected endpoints return 401 without a token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        with patch("copilot_core.api.security.get_auth_token", return_value="required-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            for method, path in self.PROTECTED_ENDPOINTS:
                with self.subTest(method=method, path=path):
                    if method == "GET":
                        r = self.client.get(path)
                    elif method == "POST":
                        r = self.client.post(path, json={})
                    # Accept 401, 404 (endpoint may not exist in minimal app), but NOT 200
                    self.assertNotEqual(
                        r.status_code, 200,
                        f"{method} {path} returned 200 without token — auth not enforced!"
                    )
                    if r.status_code not in (404, 405, 503):
                        self.assertEqual(
                            r.status_code, 401,
                            f"{method} {path} returned {r.status_code}, expected 401"
                        )

    def test_valid_token_x_auth_token_allows_access(self):
        """Valid X-Auth-Token header allows access to protected endpoints."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        with patch("copilot_core.api.security.get_auth_token", return_value="correct-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get(
                "/api/v1/events",
                headers={"X-Auth-Token": "correct-token"}
            )
        # Should NOT be 401 (may be 200, 503, 404 depending on state)
        self.assertNotEqual(r.status_code, 401, "Valid X-Auth-Token was rejected")

    def test_valid_bearer_token_allows_access(self):
        """Valid Authorization: Bearer token allows access to protected endpoints."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        with patch("copilot_core.api.security.get_auth_token", return_value="bearer-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get(
                "/api/v1/events",
                headers={"Authorization": "Bearer bearer-token"}
            )
        self.assertNotEqual(r.status_code, 401, "Valid Bearer token was rejected")

    def test_invalid_token_rejected(self):
        """Invalid token returns 401."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        with patch("copilot_core.api.security.get_auth_token", return_value="correct-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get(
                "/api/v1/events",
                headers={"X-Auth-Token": "wrong-token"}
            )
        self.assertEqual(r.status_code, 401)

    def test_partial_bearer_prefix_rejected(self):
        """Bearer prefix without token is rejected."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        with patch("copilot_core.api.security.get_auth_token", return_value="correct-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = self.client.get(
                "/api/v1/events",
                headers={"Authorization": "Bearer "}
            )
        self.assertEqual(r.status_code, 401)

    def test_no_auth_required_allows_all(self):
        """When auth_required=False, all requests pass."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        with patch("copilot_core.api.security.is_auth_required", return_value=False):
            r = self.client.get("/api/v1/events")
        self.assertNotEqual(r.status_code, 401)


class TestRequireTokenDecorator(unittest.TestCase):
    """Test the @require_token decorator directly."""

    def test_require_token_blocks_unauthenticated(self):
        """@require_token returns 401 JSON when token is invalid."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from flask import Flask
        from copilot_core.api.security import require_token

        app = Flask("test")

        @app.route("/protected")
        @require_token
        def protected():
            return "ok", 200

        client = app.test_client()
        with patch("copilot_core.api.security.get_auth_token", return_value="secret"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = client.get("/protected")

        self.assertEqual(r.status_code, 401)
        body = r.get_json()
        self.assertFalse(body.get("ok", True))
        self.assertIn("Authentication required", body.get("error", ""))

    def test_require_token_passes_authenticated(self):
        """@require_token allows request when token is valid."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from flask import Flask
        from copilot_core.api.security import require_token

        app = Flask("test")

        @app.route("/protected")
        @require_token
        def protected():
            return "ok", 200

        client = app.test_client()
        with patch("copilot_core.api.security.get_auth_token", return_value="secret"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = client.get("/protected", headers={"X-Auth-Token": "secret"})

        self.assertEqual(r.status_code, 200)

    def test_optional_token_sets_g_token_valid(self):
        """@optional_token sets g.token_valid correctly."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from flask import Flask, g
        from copilot_core.api.security import optional_token

        app = Flask("test")

        @app.route("/optional")
        @optional_token
        def optional():
            return str(g.token_valid), 200

        client = app.test_client()
        with patch("copilot_core.api.security.get_auth_token", return_value="secret"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            # Without token
            r = client.get("/optional")
            self.assertEqual(r.data, b"False")

            # With valid token
            r = client.get("/optional", headers={"X-Auth-Token": "secret"})
            self.assertEqual(r.data, b"True")


class TestAuthTokenCaching(unittest.TestCase):
    """Test token caching behavior."""

    def test_token_cached_from_env(self):
        """Token is read from COPILOT_AUTH_TOKEN env var."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.api.security as sec
        # Reset cache
        sec._token_cache = ("", 0.0)
        with patch.dict(os.environ, {"COPILOT_AUTH_TOKEN": "env-token"}):
            token = sec.get_auth_token()
        self.assertEqual(token, "env-token")

    def test_token_cache_ttl_respected(self):
        """Cached token is returned within TTL."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.api.security as sec
        import time
        sec._token_cache = ("cached-token", time.monotonic())
        token = sec.get_auth_token()
        self.assertEqual(token, "cached-token")


if __name__ == "__main__":
    unittest.main()
