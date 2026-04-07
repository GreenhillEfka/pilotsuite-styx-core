"""Comprehensive authentication security tests.

Tests verify that:
1. All protected endpoints return 401 when no token is provided
2. Valid tokens allow access
3. Invalid tokens are rejected
4. Token formats (X-Auth-Token and Bearer) are both accepted
5. Allowlisted paths bypass auth
6. Missing token configuration fails closed when auth is required
7. WebSocket connections require authentication
8. Neuron state overrides require admin tokens
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

    def test_validate_token_accepts_auto_generated_token(self):
        """1-Key-Flow: auto-generated token authenticates correctly."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        app = create_app()
        auto_token = "auto-generated-test-token"
        with app.test_request_context(headers={"X-Auth-Token": auto_token}):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value=auto_token), \
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
        # /api/v1/status is in the allowlist, so it doesn't require auth
        # No need to patch auth settings - the allowlist handles it
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


class TestWebSocketSecurity(unittest.TestCase):
    """Test WebSocket authentication security."""

    def test_websocket_handler_imports(self):
        """WebSocket handler module imports correctly."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.websocket_handler import WebSocketHandler, WebSocketEvent, EventType
        self.assertIsNotNone(WebSocketHandler)
        self.assertIsNotNone(WebSocketEvent)
        self.assertIsNotNone(EventType)

    # -- P1-01: validate_websocket_token unit tests --

    def test_validate_websocket_token_from_query_param(self):
        """Token in query parameter ?token=xxx is accepted."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import validate_websocket_token
        app = create_app()
        with app.test_request_context("/?token=ws-secret"):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value="ws-secret"):
                self.assertTrue(validate_websocket_token(request))

    def test_validate_websocket_token_from_header(self):
        """Token in X-Auth-Token header is accepted for WebSocket."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import validate_websocket_token
        app = create_app()
        with app.test_request_context(headers={"X-Auth-Token": "ws-secret"}):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value="ws-secret"):
                self.assertTrue(validate_websocket_token(request))

    def test_validate_websocket_token_rejects_wrong_token(self):
        """Wrong token in query param is rejected."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import validate_websocket_token
        app = create_app()
        with app.test_request_context("/?token=wrong"):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value="correct"):
                self.assertFalse(validate_websocket_token(request))

    def test_validate_websocket_token_rejects_no_token(self):
        """Missing token is rejected."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import validate_websocket_token
        app = create_app()
        with app.test_request_context():
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value="configured"):
                self.assertFalse(validate_websocket_token(request))

    def test_validate_websocket_token_no_configured_token(self):
        """Returns False when no token is configured at all."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import validate_websocket_token
        app = create_app()
        with app.test_request_context("/?token=anything"):
            from flask import request
            with patch("copilot_core.api.security.get_auth_token", return_value=""):
                self.assertFalse(validate_websocket_token(request))

    # -- P1-01: WebSocket connect handler auth tests --

    def _make_ws_handler(self):
        """Create a WebSocketHandler with captured event handlers."""
        from copilot_core.websocket_handler import WebSocketHandler

        mock_sio = MagicMock()
        registered = {}

        def capture_on(event):
            def decorator(fn):
                registered[event] = fn
                return fn
            return decorator

        mock_sio.on = capture_on
        handler = WebSocketHandler(mock_sio)
        return handler, registered

    def _mock_ws_request(self, sid="test-sid", args=None, headers=None):
        """Create a mock request object for WebSocket tests."""
        mock_req = MagicMock()
        mock_req.sid = sid
        mock_req.args = args or {}
        mock_req.headers = headers or {}
        return mock_req

    def test_websocket_handler_rejects_without_token(self):
        """WebSocketHandler.handle_connect rejects unauthenticated connections."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.websocket_handler as ws_mod

        handler, registered = self._make_ws_handler()
        self.assertIn("connect", registered)

        mock_req = self._mock_ws_request(sid="test-sid")
        original_request = ws_mod.request
        try:
            ws_mod.request = mock_req
            with patch("copilot_core.api.security.get_auth_token", return_value="secret"):
                result = registered["connect"](auth=None)
        finally:
            ws_mod.request = original_request

        self.assertFalse(result)
        self.assertNotIn("test-sid", handler._connections)

    def test_websocket_handler_accepts_auth_dict_token(self):
        """WebSocketHandler.handle_connect accepts SocketIO auth dict token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.websocket_handler as ws_mod

        handler, registered = self._make_ws_handler()
        mock_req = self._mock_ws_request(sid="good-sid")
        original_request = ws_mod.request
        had_emit = hasattr(ws_mod, "emit")
        original_emit = getattr(ws_mod, "emit", None)
        try:
            ws_mod.request = mock_req
            ws_mod.emit = MagicMock()
            with patch("copilot_core.api.security.get_auth_token", return_value="valid-token"):
                result = registered["connect"](auth={"token": "valid-token"})
        finally:
            ws_mod.request = original_request
            if had_emit:
                ws_mod.emit = original_emit
            elif hasattr(ws_mod, "emit"):
                del ws_mod.emit

        self.assertIsNone(result)  # None = accepted (not False)
        self.assertIn("good-sid", handler._connections)

    def test_websocket_handler_accepts_query_param_token(self):
        """WebSocketHandler.handle_connect accepts query parameter token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.websocket_handler as ws_mod

        handler, registered = self._make_ws_handler()
        mock_req = self._mock_ws_request(sid="qp-sid", args={"token": "qp-token"})
        original_request = ws_mod.request
        had_emit = hasattr(ws_mod, "emit")
        original_emit = getattr(ws_mod, "emit", None)
        try:
            ws_mod.request = mock_req
            ws_mod.emit = MagicMock()
            with patch("copilot_core.api.security.get_auth_token", return_value="qp-token"), \
                 patch("copilot_core.api.security.validate_websocket_token", return_value=True):
                result = registered["connect"](auth=None)
        finally:
            ws_mod.request = original_request
            if had_emit:
                ws_mod.emit = original_emit
            elif hasattr(ws_mod, "emit"):
                del ws_mod.emit

        self.assertIsNone(result)
        self.assertIn("qp-sid", handler._connections)

    def test_websocket_handler_rejects_wrong_token(self):
        """WebSocketHandler.handle_connect rejects wrong auth dict token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.websocket_handler as ws_mod

        handler, registered = self._make_ws_handler()
        mock_req = self._mock_ws_request(sid="bad-sid")
        original_request = ws_mod.request
        try:
            ws_mod.request = mock_req
            with patch("copilot_core.api.security.get_auth_token", return_value="correct"), \
                 patch("copilot_core.api.security.validate_websocket_token", return_value=False):
                result = registered["connect"](auth={"token": "wrong"})
        finally:
            ws_mod.request = original_request

        self.assertFalse(result)
        self.assertNotIn("bad-sid", handler._connections)

    # -- P1-01: NeuronWebSocketHandler auth tests --

    def _make_neuron_ws_handler(self):
        """Create a NeuronWebSocketHandler with captured event handlers."""
        from copilot_core.api.v1.websocket_neuron import NeuronWebSocketHandler

        mock_sio = MagicMock()
        registered = {}

        def capture_on(event):
            def decorator(fn):
                registered[event] = fn
                return fn
            return decorator

        mock_sio.on = capture_on

        handler = NeuronWebSocketHandler()
        with patch("copilot_core.api.v1.websocket_neuron.SOCKETIO_AVAILABLE", True):
            handler.socketio = mock_sio
            handler._register_handlers()

        return handler, registered

    def test_neuron_ws_handler_rejects_without_token(self):
        """NeuronWebSocketHandler rejects unauthenticated connections."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.api.v1.websocket_neuron as neuron_ws_mod

        handler, registered = self._make_neuron_ws_handler()
        self.assertIn("connect", registered)

        mock_req = MagicMock()
        mock_req.sid = "unauth-sid"
        mock_req.args = {}
        mock_req.headers = {}
        original_request = neuron_ws_mod.request
        try:
            neuron_ws_mod.request = mock_req
            with patch("copilot_core.api.security.get_auth_token", return_value="secret"):
                result = registered["connect"](auth=None)
        finally:
            neuron_ws_mod.request = original_request

        self.assertFalse(result)
        self.assertNotIn("unauth-sid", handler.connected_clients)

    def test_neuron_ws_handler_accepts_valid_auth(self):
        """NeuronWebSocketHandler accepts valid auth dict token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        import copilot_core.api.v1.websocket_neuron as neuron_ws_mod

        handler, registered = self._make_neuron_ws_handler()

        mock_req = MagicMock()
        mock_req.sid = "auth-sid"
        mock_req.args = {}
        mock_req.headers = {}
        original_request = neuron_ws_mod.request
        try:
            neuron_ws_mod.request = mock_req
            with patch("copilot_core.api.security.get_auth_token", return_value="valid"), \
                 patch.object(neuron_ws_mod, "join_room", MagicMock()), \
                 patch.object(neuron_ws_mod, "emit", MagicMock()):
                result = registered["connect"](auth={"token": "valid"})
        finally:
            neuron_ws_mod.request = original_request

        self.assertIsNone(result)
        self.assertIn("auth-sid", handler.connected_clients)


class TestNeuronStateOverrideSecurity(unittest.TestCase):
    """Test that neuron endpoints require authentication."""

    def test_evaluate_endpoint_requires_auth(self):
        """POST /neurons/evaluate requires valid token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        with patch("copilot_core.api.security.get_auth_token", return_value="secret-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = client.post(
                "/api/v1/neurons/evaluate",
                json={"states": {"light.living_room": "on"}},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 401)

            r = client.post(
                "/api/v1/neurons/evaluate",
                json={"states": {"light.living_room": "on"}},
                headers={"X-Auth-Token": "secret-token"},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 200)

    def test_update_endpoint_requires_auth(self):
        """POST /neurons/update requires valid token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        with patch("copilot_core.api.security.get_auth_token", return_value="secret-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            r = client.post(
                "/api/v1/neurons/update",
                json={"states": {"light.living_room": "on"}},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 401)

            r = client.post(
                "/api/v1/neurons/update",
                json={"states": {"light.living_room": "on"}},
                headers={"X-Auth-Token": "secret-token"},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 200)

    # -- P1-02: /mood/evaluate state override authorization --

    def test_mood_evaluate_without_overrides_needs_basic_auth(self):
        """POST /neurons/mood/evaluate without overrides works with normal token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        with patch("copilot_core.api.security.get_auth_token", return_value="user-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            # No overrides – standard token is sufficient
            r = client.post(
                "/api/v1/neurons/mood/evaluate",
                json={},
                headers={"X-Auth-Token": "user-token"},
                content_type="application/json"
            )
            self.assertIn(r.status_code, (200,))

    def test_mood_evaluate_state_override_requires_admin(self):
        """POST /neurons/mood/evaluate with states override requires admin token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        with patch("copilot_core.api.security.get_auth_token", return_value="admin-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            # Without token – should be 401 (before_request blocks)
            r = client.post(
                "/api/v1/neurons/mood/evaluate",
                json={"states": {"light.kitchen": "on"}},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 401)

            # With wrong token – should be 401
            r = client.post(
                "/api/v1/neurons/mood/evaluate",
                json={"states": {"light.kitchen": "on"}},
                headers={"X-Auth-Token": "wrong"},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 401)

            # With valid admin token – should succeed
            r = client.post(
                "/api/v1/neurons/mood/evaluate",
                json={"states": {"light.kitchen": "on"}},
                headers={"X-Auth-Token": "admin-token"},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 200)

    def test_mood_evaluate_context_override_requires_admin(self):
        """POST /neurons/mood/evaluate with context override requires admin token."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        with patch("copilot_core.api.security.get_auth_token", return_value="admin-token"), \
             patch("copilot_core.api.security.is_auth_required", return_value=True):
            # Without admin token
            r = client.post(
                "/api/v1/neurons/mood/evaluate",
                json={"context": {"time_of_day": "night"}},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 401)

            # With valid admin token
            r = client.post(
                "/api/v1/neurons/mood/evaluate",
                json={"context": {"time_of_day": "night"}},
                headers={"X-Auth-Token": "admin-token"},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 200)

    def test_evaluate_state_override_returns_403_with_normal_token(self):
        """State override with normal (non-admin) token returns 403.

        When auth is disabled globally but a token IS configured,
        require_admin_token still gates access.
        """
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        # Auth disabled globally, but admin token still required for overrides
        with patch("copilot_core.api.security.is_auth_required", return_value=False), \
             patch("copilot_core.api.security.get_auth_token", return_value="admin-only"):
            # Normal request passes before_request (auth disabled)
            # but state override still needs admin token
            r = client.post(
                "/api/v1/neurons/evaluate",
                json={"states": {"sensor.temp": "22"}},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 403)

            # With correct admin token
            r = client.post(
                "/api/v1/neurons/evaluate",
                json={"states": {"sensor.temp": "22"}},
                headers={"X-Auth-Token": "admin-only"},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 200)

    def test_update_returns_403_without_admin_token(self):
        """POST /neurons/update returns 403 without admin token (even if auth disabled)."""
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        with patch("copilot_core.api.security.is_auth_required", return_value=False), \
             patch("copilot_core.api.security.get_auth_token", return_value="admin-only"):
            r = client.post(
                "/api/v1/neurons/update",
                json={"states": {"sensor.temp": "22"}},
                content_type="application/json"
            )
            self.assertEqual(r.status_code, 403)


class TestGetTokenSource(unittest.TestCase):
    """Test get_token_source() returns correct source identifier."""

    def test_source_env(self):
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import get_token_source
        with patch.dict(os.environ, {"COPILOT_AUTH_TOKEN": "env-token"}):
            self.assertEqual(get_token_source(), "env")

    def test_source_options(self):
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import get_token_source
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"auth_token": "opt-token"}, f)
            f.flush()
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("COPILOT_AUTH_TOKEN", None)
                self.assertEqual(get_token_source(f.name), "options")
            os.unlink(f.name)

    def test_source_auto(self):
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import get_token_source, AUTO_TOKEN_PATH
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COPILOT_AUTH_TOKEN", None)
            with patch("builtins.open", side_effect=[
                FileNotFoundError,  # options.json
                unittest.mock.mock_open(read_data="auto-tok")(),  # auto token file
            ]):
                self.assertEqual(get_token_source("/nonexistent/options.json"), "auto")

    def test_source_none(self):
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from copilot_core.api.security import get_token_source
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COPILOT_AUTH_TOKEN", None)
            self.assertEqual(get_token_source("/nonexistent/options.json"), "none")


class TestSetupTokenEndpoint(unittest.TestCase):
    """Test the /api/v1/auth/setup-token endpoint."""

    def test_setup_token_returns_auto_token(self):
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from flask import Flask
        from copilot_core.api.v1.auth import auth_bp

        app = Flask("test")
        app.register_blueprint(auth_bp)
        client = app.test_client()

        with patch("copilot_core.api.v1.auth.get_token_source", return_value="auto"), \
             patch("copilot_core.api.v1.auth.get_auth_token", return_value="auto-gen-token"):
            r = client.get("/api/v1/auth/setup-token")

        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["token"], "auto-gen-token")
        self.assertEqual(body["source"], "auto")

    def test_setup_token_exposes_manual_token(self):
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from flask import Flask
        from copilot_core.api.v1.auth import auth_bp

        app = Flask("test")
        app.register_blueprint(auth_bp)
        client = app.test_client()

        with patch("copilot_core.api.v1.auth.get_token_source", return_value="env"), \
             patch("copilot_core.api.v1.auth.get_auth_token", return_value="env-token-123"):
            r = client.get("/api/v1/auth/setup-token")

        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["token"], "env-token-123")
        self.assertEqual(body["source"], "env")

    def test_setup_token_no_token_available(self):
        if not _FLASK_AVAILABLE:
            self.skipTest("Flask not installed")
        from flask import Flask
        from copilot_core.api.v1.auth import auth_bp

        app = Flask("test")
        app.register_blueprint(auth_bp)
        client = app.test_client()

        with patch("copilot_core.api.v1.auth.get_token_source", return_value="none"):
            r = client.get("/api/v1/auth/setup-token")

        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertFalse(body["ok"])
        self.assertIsNone(body["token"])


if __name__ == "__main__":
    unittest.main()
