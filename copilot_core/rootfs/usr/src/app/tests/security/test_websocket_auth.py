"""Security Tests: WebSocket Authentication (P1-01).

Tests for WebSocket authentication requirements.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from copilot_core.api.security import validate_websocket_token, get_auth_token, require_admin_token


class TestWebSocketAuthentication:
    """Test WebSocket authentication (P1-01)."""
    
    def test_websocket_token_from_query_param(self):
        """Test token validation from query parameter."""
        mock_request = Mock()
        mock_request.args = {"token": "test_token_123"}
        mock_request.headers = {}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="test_token_123"):
            result = validate_websocket_token(mock_request)
            assert result is True
    
    def test_websocket_token_from_header(self):
        """Test token validation from X-Auth-Token header."""
        mock_request = Mock()
        mock_request.args = {}
        mock_request.headers = {"X-Auth-Token": "test_token_123"}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="test_token_123"):
            result = validate_websocket_token(mock_request)
            assert result is True
    
    def test_websocket_rejects_missing_token(self):
        """Test that connections without token are rejected."""
        mock_request = Mock()
        mock_request.args = {}
        mock_request.headers = {}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="test_token_123"):
            result = validate_websocket_token(mock_request)
            assert result is False
    
    def test_websocket_rejects_invalid_token(self):
        """Test that invalid tokens are rejected."""
        mock_request = Mock()
        mock_request.args = {"token": "wrong_token"}
        mock_request.headers = {}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="test_token_123"):
            result = validate_websocket_token(mock_request)
            assert result is False
    
    def test_websocket_no_configured_token(self):
        """Test behavior when no token is configured."""
        mock_request = Mock()
        mock_request.args = {}
        mock_request.headers = {}
        
        with patch('copilot_core.api.security.get_auth_token', return_value=""):
            result = validate_websocket_token(mock_request)
            assert result is False  # Cannot validate without configured token


class TestAdminTokenRequirement:
    """Test admin token requirements for sensitive operations (P1-02)."""
    
    def test_admin_token_from_header(self):
        """Test admin token validation from header."""
        mock_request = Mock()
        mock_request.headers = {"X-Auth-Token": "admin_token_123"}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="admin_token_123"):
            result = require_admin_token(mock_request)
            assert result is True
    
    def test_admin_token_from_bearer(self):
        """Test admin token validation from Bearer header."""
        mock_request = Mock()
        mock_request.headers = {"Authorization": "Bearer admin_token_123"}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="admin_token_123"):
            result = require_admin_token(mock_request)
            assert result is True
    
    def test_admin_rejects_missing_token(self):
        """Test that admin operations reject missing tokens."""
        mock_request = Mock()
        mock_request.headers = {}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="admin_token_123"):
            result = require_admin_token(mock_request)
            assert result is False
    
    def test_admin_rejects_invalid_token(self):
        """Test that admin operations reject invalid tokens."""
        mock_request = Mock()
        mock_request.headers = {"X-Auth-Token": "wrong_token"}
        
        with patch('copilot_core.api.security.get_auth_token', return_value="admin_token_123"):
            result = require_admin_token(mock_request)
            assert result is False
    
    def test_admin_always_requires_token(self):
        """Test that admin operations ALWAYS require token, even if auth disabled."""
        mock_request = Mock()
        mock_request.headers = {}
        
        # Even with no token configured, admin operations should fail
        with patch('copilot_core.api.security.get_auth_token', return_value=""):
            result = require_admin_token(mock_request)
            assert result is False


class TestFailedAuthLogging:
    """Test failed authentication logging (P3-02)."""

    def test_validate_token_returns_false_on_failure(self):
        """Test that failed token validation returns False and logs."""
        from copilot_core.api import security

        mock_request = Mock()
        mock_request.headers = {"X-Auth-Token": "wrong_token"}
        mock_request.remote_addr = "192.168.1.100"
        mock_request.path = "/api/v1/test"
        mock_request.method = "POST"

        with patch.dict(os.environ, {"COPILOT_AUTH_REQUIRED": "true"}):
            with patch.object(security, 'get_auth_token', return_value="correct_token"):
                result = security.validate_token(mock_request)
                assert result is False  # Should reject invalid token


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
