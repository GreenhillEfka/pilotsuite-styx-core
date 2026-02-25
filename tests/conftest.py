"""
pytest configuration for PilotSuite Styx Core test suite.
"""

import pytest
import os

# Global fixture for API base URL (can be overridden via env)
@pytest.fixture(scope="session")
def api_base_url():
    """Base URL for the Copilot Core API."""
    return os.getenv("API_BASE_URL", "http://localhost:8123/api")

# Global fixture for SearXNG endpoint
@pytest.fixture(scope="session")
def searxng_url():
    """URL for SearXNG service."""
    return os.getenv("SEARXNG_URL", "http://192.168.30.18:4041")

# Marker fixture for slow tests
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "regression: regression tests")
    config.addinivalue_line("markers", "e2e: end-to-end tests")
    config.addinivalue_line("markers", "slow: slow running tests")
