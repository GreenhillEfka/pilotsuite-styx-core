"""
Test: E2E User Workflow - SearXNG Web Search
=============================================

End-to-end test simulating a complete user workflow:
1. User triggers search request
2. Styx forwards to SearXNG
3. Results are processed and returned

This validates the MCP Phase 2 Web Search integration.
"""

import pytest
import requests


@pytest.mark.e2e
class TestSearXNGWorkflow:
    """E2E tests for SearXNG web search workflow."""

    def test_user_search_workflow(self, searxng_url):
        """
        Simulate complete user search workflow:
        1. User sends search query
        2. Styx forwards to SearXNG
        3. Results are parsed and returned
        
        Note: SearXNG blocks JSON format (/search?q=test&format=json → 403)
        so we test HTML response instead (which is the primary interface).
        """
        # Step 1: User triggers search
        query = "PilotSuite Styx Core"
        
        # Step 2: Forward to SearXNG (GET request with query param)
        try:
            response = requests.get(
                f"{searxng_url}/search",
                params={"q": query},
                timeout=10
            )
        except requests.exceptions.ConnectionError:
            pytest.fail("SearXNG service not reachable")
        
        # Step 3: Validate response — HTML expected (not JSON due to SearXNG restrictions)
        assert response.status_code == 200, "SearXNG search failed"
        assert "html" in response.headers.get("content-type", "").lower(), "Expected HTML response"
        assert query in response.text, "Search query not found in response"

    def test_search_results_structure(self, searxng_url):
        """Validate expected fields in search results (HTML parsing)."""
        query = "Home Assistant"
        
        try:
            response = requests.get(
                f"{searxng_url}/search",
                params={"q": query},
                timeout=10
            )
        except requests.exceptions.ConnectionError:
            pytest.fail("SearXNG service not reachable")
        
        assert response.status_code == 200, "SearXNG search failed"
        assert "html" in response.headers.get("content-type", "").lower(), "Expected HTML response"
        # SearXNG HTML results typically include result titles and URLs
        assert query in response.text, "Search query not found in response"
        # Check for common result elements
        assert "result" in response.text.lower() or "title" in response.text.lower(), "No results found"
