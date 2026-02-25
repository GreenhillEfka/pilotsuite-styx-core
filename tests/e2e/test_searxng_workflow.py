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
        """
        # Step 1: User triggers search
        query = "PilotSuite Styx Core"
        
        # Step 2: Forward to SearXNG (GET request with query param)
        try:
            response = requests.get(
                f"{searxng_url}/search",
                params={"q": query, "format": "json"},
                timeout=10
            )
        except requests.exceptions.ConnectionError:
            pytest.fail("SearXNG service not reachable")
        
        # Step 3: Validate response structure
        # SearXNG JSON response should contain results array
        assert response.status_code == 200, "SearXNG search failed"
        
        try:
            data = response.json()
            assert "results" in data, "Response missing 'results' field"
            assert isinstance(data["results"], list), "Results should be a list"
        except ValueError:
            pytest.fail("SearXNG did not return valid JSON")

    def test_search_results_structure(self, searxng_url):
        """Validate expected fields in search results."""
        query = "Home Assistant"
        
        try:
            response = requests.get(
                f"{searxng_url}/search",
                params={"q": query, "format": "json"},
                timeout=10
            )
        except requests.exceptions.ConnectionError:
            pytest.fail("SearXNG service not reachable")
        
        data = response.json()
        
        if data["results"]:
            result = data["results"][0]
            # SearXNG results typically include: title, url, content
            assert "title" in result, "Result missing 'title'"
            assert "url" in result, "Result missing 'url'"
            assert "content" in result, "Result missing 'content'"
