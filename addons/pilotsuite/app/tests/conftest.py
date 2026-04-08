"""Shared test fixtures for CoPilot Core tests."""
import pytest


@pytest.fixture(autouse=True)
def reset_auth_token_cache():
    """Reset the auth token cache before each test.

    Prevents token state leaking between test modules — the cache is a
    module-level variable with a 60s TTL, so a test that sets it will
    poison all subsequent tests that create a Flask test client.
    """
    try:
        import copilot_core.api.security as sec
        sec._token_cache = ("", 0.0)
    except ImportError:
        pass
    yield
    # Also reset after the test
    try:
        import copilot_core.api.security as sec
        sec._token_cache = ("", 0.0)
    except ImportError:
        pass
