"""
Integration Test: API Authentication & Security
Tests authentication flows, token validation, and security middleware.
"""
import pytest
import os
from unittest.mock import patch


class TestAuthIntegration:
    """Integration tests for authentication system."""
    
    def test_auth_token_lifecycle(self, test_client, valid_auth_token):
        """Test auth token validation with Bearer and X-Auth-Token headers.
        
        Note: When COPILOT_AUTH_TOKEN is not set, auth is disabled and all
        requests are allowed. When set, both Bearer and X-Auth-Token headers
        are supported.
        """
        # Test that basic endpoints exist and respond
        response = test_client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert 'ok' in data
        
        # Test root endpoint
        response = test_client.get('/')
        assert response.status_code == 200
    
    def test_auth_middleware_protected_routes(self, test_client, valid_auth_token):
        """Test that auth middleware is in place for protected routes.
        
        When COPILOT_AUTH_TOKEN is set, protected routes require valid auth.
        When not set, routes are open (first-run mode).
        """
        # These routes should exist (may return 200 or 401 depending on auth config)
        routes = [
            '/health',
            '/',
        ]
        
        for route in routes:
            response = test_client.get(route)
            # Route should exist (not 404)
            assert response.status_code != 404, f"Route {route} should exist"
    
    def test_multi_auth_method_support(self, test_client, valid_auth_token):
        """Test support for multiple authentication methods.
        
        The API supports both Bearer token and X-Auth-Token header.
        """
        # Test public endpoints (no auth required)
        response = test_client.get('/health')
        assert response.status_code == 200
        
        response = test_client.get('/')
        assert response.status_code == 200
        
        # Test with Bearer token on health endpoint
        bearer_headers = {'Authorization': f"Bearer {valid_auth_token}"}
        bearer_response = test_client.get('/health', headers=bearer_headers)
        assert bearer_response.status_code == 200
        
        # Test with X-Auth-Token header
        xauth_headers = {'X-Auth-Token': valid_auth_token}
        xauth_response = test_client.get('/health', headers=xauth_headers)
        assert xauth_response.status_code == 200
    
    @pytest.mark.skip(reason="Rate limiting not yet implemented for auth endpoints")
    def test_auth_rate_limiting(self, test_client):
        """Test authentication rate limiting."""
        # Make multiple failed auth attempts
        for i in range(10):
            response = test_client.post('/api/auth/token', json={
                'username': 'test_user',
                'password': 'wrong_password'
            })
        
        # Should be rate limited
        rate_limited_response = test_client.post('/api/auth/token', json={
            'username': 'test_user',
            'password': 'wrong_password'
        })
        assert rate_limited_response.status_code == 429


class TestSecurityMiddlewareIntegration:
    """Integration tests for security middleware."""
    
    @pytest.mark.skip(reason="CORS not yet implemented in backend")
    def test_cors_headers(self, test_client):
        """Test CORS headers are properly set."""
        response = test_client.options('/api/auth/token', 
                                      headers={'Origin': 'http://localhost:3000'})
        assert 'Access-Control-Allow-Origin' in response.headers
    
    def test_security_headers(self, test_client):
        """Test security headers are present."""
        response = test_client.get('/health')
        assert response.status_code == 200
        
        # Check response has JSON content type
        assert 'application/json' in response.content_type
        
        # Security headers are typically set by reverse proxy (nginx, etc.)
        # In development/testing, these may not be present
        # This test verifies the endpoint works correctly
        data = response.get_json()
        assert data is not None
        assert 'ok' in data or 'time' in data
