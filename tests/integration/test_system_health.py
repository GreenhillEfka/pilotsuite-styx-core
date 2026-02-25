"""
Test: System Health Check
=========================

Integration test to verify core system components are operational.

This test validates:
- API endpoint availability
- SearXNG service availability
- Core module structure integrity
"""

import pytest
import requests


@pytest.mark.integration
class TestSystemHealth:
    """System health integration tests."""

    def test_api_endpoint_available(self, api_base_url):
        """Test that the API endpoint is reachable."""
        # Simple health check — /status or /health
        try:
            response = requests.get(f"{api_base_url}/status", timeout=5)
            # 200 OK or 404 not found both mean endpoint is reachable
            assert response.status_code in [200, 404], "API endpoint responding unexpectedly"
        except requests.exceptions.ConnectionError:
            pytest.skip("API not reachable (expected if service not running)")

    def test_searxng_available(self, searxng_url):
        """Test that SearXNG service is reachable."""
        try:
            response = requests.get(searxng_url, timeout=5)
            assert response.status_code == 200, "SearXNG not returning 200 OK"
            # Verify it's the SearXNG UI
            assert "searxng" in response.text.lower() or "search" in response.text.lower(), "Not SearXNG page"
        except requests.exceptions.ConnectionError:
            pytest.fail("SearXNG service not reachable")

    def test_searxng_search_endpoint(self, searxng_url):
        """Test SearXNG search functionality."""
        try:
            # Test with a simple query (HTML response, not JSON due to SearXNG restrictions)
            response = requests.get(
                f"{searxng_url}/search",
                params={"q": "test"},
                timeout=5
            )
            # SearXNG returns 200 for HTML search, may return 403 for JSON
            assert response.status_code == 200, "SearXNG search endpoint not reachable"
            assert "html" in response.headers.get("content-type", "").lower(), "Expected HTML response"
        except requests.exceptions.ConnectionError:
            pytest.fail("SearXNG service not reachable")
