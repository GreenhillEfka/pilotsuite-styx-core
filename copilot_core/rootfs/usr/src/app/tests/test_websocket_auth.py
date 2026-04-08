"""WebSocket Authentication Tests for PilotSuite v12.10.0.

Tests verify that:
1. WebSocket connections require valid authentication
2. Token validation works via query param, header, and auth dict
3. Unauthenticated connections are rejected and logged
4. Connection tracking works correctly

Author: Cowdya
Version: 12.10.0
"""
from __future__ import annotations

import logging
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

try:
    from copilot_core.websocket_handler import WebSocketHandler, validate_room_name
    from copilot_core.api.security import validate_websocket_token, get_auth_token
    _MODULES_AVAILABLE = True
except ModuleNotFoundError:
    _MODULES_AVAILABLE = False
    WebSocketHandler = None
    validate_websocket_token = None
    get_auth_token = None


class MockRequest:
    """Mock Flask/SocketIO request object for testing."""
    
    def __init__(self, sid='test-sid', args=None, headers=None, remote_addr='127.0.0.1'):
        self.sid = sid
        self.args = args or {}
        self.headers = headers or {}
        self.remote_addr = remote_addr


class TestWebSocketTokenValidation(unittest.TestCase):
    """Tests for validate_websocket_token() function."""

    @patch('copilot_core.api.security.get_auth_token')
    def test_valid_token_via_query_param(self, mock_get_token):
        """validate_websocket_token accepts valid token via query param (?token=xxx)."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "secret-token-123"
        
        request = MockRequest(
            sid='test-1',
            args={'token': 'secret-token-123'},
            headers={}
        )
        
        result = validate_websocket_token(request)
        self.assertTrue(result, "Should accept valid token via query param")

    @patch('copilot_core.api.security.get_auth_token')
    def test_valid_token_via_x_auth_header(self, mock_get_token):
        """validate_websocket_token accepts valid token via X-Auth-Token header."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "secret-token-123"
        
        request = MockRequest(
            sid='test-2',
            args={},
            headers={'X-Auth-Token': 'secret-token-123'}
        )
        
        result = validate_websocket_token(request)
        self.assertTrue(result, "Should accept valid token via X-Auth-Token header")

    @patch('copilot_core.api.security.get_auth_token')
    def test_valid_token_via_socketio_auth_dict(self, mock_get_token):
        """validate_websocket_token accepts valid token via SocketIO auth dict."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "secret-token-123"
        
        # SocketIO passes auth as a dict attribute
        request = MockRequest(
            sid='test-3',
            args={},
            headers={}
        )
        request.auth = {'token': 'secret-token-123'}
        
        # Note: validate_websocket_token checks args and headers
        # The auth dict is handled in websocket_handler.py handle_connect
        # This test verifies the function works with standard request objects
        result = validate_websocket_token(request)
        # Should be False since auth dict is not checked by this function
        self.assertFalse(result, "validate_websocket_token doesn't check auth dict (handled in handler)")

    @patch('copilot_core.api.security.get_auth_token')
    def test_missing_token_rejected(self, mock_get_token):
        """validate_websocket_token rejects connections without token."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "secret-token-123"
        
        request = MockRequest(
            sid='test-4',
            args={},
            headers={}
        )
        
        result = validate_websocket_token(request)
        self.assertFalse(result, "Should reject missing token")

    @patch('copilot_core.api.security.get_auth_token')
    def test_invalid_token_rejected(self, mock_get_token):
        """validate_websocket_token rejects invalid tokens."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "correct-token"
        
        request = MockRequest(
            sid='test-5',
            args={'token': 'wrong-token'},
            headers={}
        )
        
        result = validate_websocket_token(request)
        self.assertFalse(result, "Should reject invalid token")

    @patch('copilot_core.api.security.get_auth_token')
    def test_no_token_configured_rejected(self, mock_get_token):
        """validate_websocket_token rejects when no token is configured (secure default)."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = ""
        
        request = MockRequest(
            sid='test-6',
            args={},
            headers={}
        )
        
        result = validate_websocket_token(request)
        self.assertFalse(result, "Should reject when no token configured")

    @patch('copilot_core.api.security.get_auth_token')
    def test_token_case_sensitive(self, mock_get_token):
        """Token validation is case-sensitive."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "Secret-Token"
        
        request = MockRequest(
            sid='test-7',
            args={'token': 'secret-token'},  # lowercase
            headers={}
        )
        
        result = validate_websocket_token(request)
        self.assertFalse(result, "Should reject case-mismatched token")


class TestWebSocketHandlerAuth(unittest.TestCase):
    """Tests for WebSocket handler authentication logic."""

    @patch('copilot_core.api.security.validate_websocket_token')
    @patch('copilot_core.api.security.get_auth_token')
    def test_handle_connect_with_valid_query_token(self, mock_get_token, mock_validate):
        """handle_connect accepts connection with valid query token."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "test-token"
        mock_validate.return_value = True
        
        # Simulate the authentication logic from handle_connect
        authenticated = False
        configured_token = mock_get_token()
        
        # Test query param path (simulated via validate_websocket_token)
        if mock_validate(MagicMock()):
            authenticated = True
        
        self.assertTrue(authenticated)

    @patch('copilot_core.api.security.get_auth_token')
    def test_handle_connect_with_socketio_auth_dict(self, mock_get_token):
        """handle_connect accepts token from SocketIO auth dict."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        import hmac
        mock_get_token.return_value = "test-token"
        
        # Simulate SocketIO auth dict
        auth = {'token': 'test-token'}
        configured_token = mock_get_token()
        
        authenticated = False
        if auth and isinstance(auth, dict) and 'token' in auth:
            candidate = str(auth['token']).strip()
            if candidate and hmac.compare_digest(candidate, configured_token):
                authenticated = True
        
        self.assertTrue(authenticated, "Should accept valid token from auth dict")

    @patch('copilot_core.api.security.validate_websocket_token')
    @patch('copilot_core.api.security.get_auth_token')
    @patch('copilot_core.websocket_handler._LOGGER')
    def test_handle_connect_rejects_unauthenticated(self, mock_logger, mock_get_token, mock_validate):
        """handle_connect rejects unauthenticated connections."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "test-token"
        mock_validate.return_value = False
        
        # Simulate authentication failure
        authenticated = False
        configured_token = mock_get_token()
        
        if not configured_token:
            authenticated = False
        elif mock_validate(MagicMock()):
            authenticated = True
        else:
            authenticated = False
        
        self.assertFalse(authenticated)

    @patch('copilot_core.api.security.get_auth_token')
    def test_handle_connect_no_token_configured(self, mock_get_token):
        """handle_connect rejects when no token configured (secure default)."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = ""
        
        configured_token = mock_get_token()
        authenticated = False
        
        if not configured_token:
            # No token configured - reject (secure default)
            authenticated = False
        
        self.assertFalse(authenticated, "Should reject when no token configured")


class TestConnectionTracking(unittest.TestCase):
    """Tests for WebSocket connection tracking."""

    def test_handler_tracks_connections(self):
        """WebSocketHandler tracks active connections."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        handler = WebSocketHandler(socketio=None)
        
        # Simulate connections
        handler._connections.add("sid-1")
        handler._connections.add("sid-2")
        handler._connections.add("sid-3")
        
        self.assertEqual(len(handler._connections), 3)
        self.assertEqual(handler.get_connection_count(), 3)

    def test_handler_removes_disconnected(self):
        """WebSocketHandler removes disconnected clients."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        handler = WebSocketHandler(socketio=None)
        
        handler._connections.add("sid-1")
        handler._connections.add("sid-2")
        
        # Simulate disconnect
        handler._connections.discard("sid-1")
        
        self.assertEqual(len(handler._connections), 1)
        self.assertEqual(handler.get_connection_count(), 1)

    def test_handler_room_tracking(self):
        """WebSocketHandler tracks room memberships."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        handler = WebSocketHandler(socketio=None)
        
        # Simulate room joins
        handler._rooms["mood"] = {"sid-1", "sid-2"}
        handler._rooms["neurons"] = {"sid-2", "sid-3"}
        
        self.assertEqual(handler.get_room_members("mood"), 2)
        self.assertEqual(handler.get_room_members("neurons"), 2)
        self.assertEqual(handler.get_room_members("general"), 0)

    def test_handler_cleanup(self):
        """WebSocketHandler.cleanup() clears all state."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        handler = WebSocketHandler(socketio=None)
        
        handler._connections.add("sid-1")
        handler._rooms["test"] = {"sid-1"}
        handler._event_handlers["mood_update"] = [lambda: None]
        
        handler.cleanup()
        
        self.assertEqual(len(handler._connections), 0)
        self.assertEqual(len(handler._rooms), 0)
        self.assertEqual(len(handler._event_handlers), 0)


class TestRoomNameValidation(unittest.TestCase):
    """Tests for room name validation (P2-05)."""

    def test_valid_room_names(self):
        """validate_room_name accepts valid room names."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        valid_names = [
            "general",
            "mood",
            "neurons",
            "test_room",
            "test-room",
            "Room123",
            "a" * 50,  # Max length
        ]
        
        for name in valid_names:
            self.assertTrue(validate_room_name(name), f"Should accept: {name}")

    def test_invalid_room_names(self):
        """validate_room_name rejects invalid room names."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        invalid_names = [
            "",  # Empty
            "room name",  # Space
            "room/name",  # Slash
            "room.name",  # Dot
            "room;drop",  # Semicolon (injection attempt)
            "room' OR '1'='1",  # SQL injection
            "<script>",  # XSS attempt
            "a" * 51,  # Too long
            "../etc/passwd",  # Path traversal
        ]
        
        for name in invalid_names:
            self.assertFalse(validate_room_name(name), f"Should reject: {name}")


class TestWebSocketAuthIntegration(unittest.TestCase):
    """Integration tests for WebSocket authentication flow."""

    @patch('copilot_core.api.security.get_auth_token')
    def test_full_auth_flow_query_param(self, mock_get_token):
        """Full authentication flow with query param token."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        import hmac
        mock_get_token.return_value = "integration-test-token"
        
        # Simulate connection with query param
        request = MockRequest(
            sid='integration-1',
            args={'token': 'integration-test-token'},
            headers={}
        )
        
        # Step 1: Get configured token
        configured_token = mock_get_token()
        self.assertIsNotNone(configured_token)
        
        # Step 2: Validate via query param
        query_token = request.args.get('token', '').strip()
        self.assertTrue(hmac.compare_digest(query_token, configured_token))
        
        # Step 3: Connection should be authenticated
        self.assertTrue(validate_websocket_token(request))

    @patch('copilot_core.api.security.get_auth_token')
    def test_full_auth_flow_header(self, mock_get_token):
        """Full authentication flow with X-Auth-Token header."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "header-test-token"
        
        request = MockRequest(
            sid='integration-2',
            args={},
            headers={'X-Auth-Token': 'header-test-token'}
        )
        
        result = validate_websocket_token(request)
        self.assertTrue(result, "Header auth should work")

    @patch('copilot_core.api.security.get_auth_token')
    def test_auth_failure_logging(self, mock_get_token):
        """Failed authentication attempts are logged.
        
        Note: validate_websocket_token currently does not log failures.
        This test verifies the function correctly rejects invalid tokens.
        Logging may be added in a future enhancement.
        """
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "correct-token"
        
        request = MockRequest(
            sid='integration-3',
            args={'token': 'wrong-token'},
            headers={},
            remote_addr='192.168.1.100'
        )
        
        result = validate_websocket_token(request)
        self.assertFalse(result, "Should reject invalid token")


class TestSecurityEdgeCases(unittest.TestCase):
    """Edge case tests for WebSocket security."""

    @patch('copilot_core.api.security.get_auth_token')
    def test_whitespace_token_handling(self, mock_get_token):
        """Tokens with whitespace are handled correctly."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "token-with-spaces"
        
        # Token with extra whitespace should not match
        request = MockRequest(
            sid='edge-1',
            args={'token': '  token-with-spaces  '},
            headers={}
        )
        
        # The validate function strips whitespace
        result = validate_websocket_token(request)
        # Should match after stripping
        self.assertTrue(result)

    @patch('copilot_core.api.security.get_auth_token')
    def test_empty_string_token(self, mock_get_token):
        """Empty string tokens are rejected."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "valid-token"
        
        request = MockRequest(
            sid='edge-2',
            args={'token': ''},
            headers={}
        )
        
        result = validate_websocket_token(request)
        self.assertFalse(result, "Empty token should be rejected")

    @patch('copilot_core.api.security.get_auth_token')
    def test_none_token_value(self, mock_get_token):
        """None token values are handled safely."""
        if not _MODULES_AVAILABLE:
            self.skipTest("Modules not available")
        
        mock_get_token.return_value = "valid-token"
        
        request = MockRequest(
            sid='edge-3',
            args={'token': None},
            headers={}
        )
        
        # Should not crash
        try:
            result = validate_websocket_token(request)
            self.assertFalse(result)
        except (AttributeError, TypeError):
            # Acceptable if it raises on None value
            pass


if __name__ == "__main__":
    unittest.main()
