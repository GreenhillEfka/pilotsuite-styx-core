"""Contract tests for P0-001 token auth surface — pins intentional design.

These are integration tests via Flask test client to avoid module-level
caching issues that affect isolated unit tests with environment variables.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))


# ── Helper ───────────────────────────────────────────────────────────────────

def _make_client(token: str | None = None):
    """Create Flask test client with optional auth token header."""
    os.environ.setdefault("COPILOT_AUTH_TOKEN", "pilotclaw-test-token")
    os.environ.pop("COPILOT_AUTH_REQUIRED", None)
    from copilot_core.app import create_app
    app = create_app()
    headers = {}
    if token:
        headers["X-Auth-Token"] = token
    return app.test_client(), headers


# ── Test: /setup-token intentionally unauthenticated ─────────────────────────

@pytest.mark.skip(reason="H4-flaky-005: full-suite env context pollution — passes in isolation")
class TestSetupTokenEndpoint:
    """P0-001 Audit: /api/v1/auth/setup-token is intentionally unauthenticated.

    This endpoint is the Zero-Config / 1-Key-Flow seam: HA fetches the active
    token once during onboarding without needing a pre-existing credential.
    It is registered on the app directly (not via api_v1 blueprint).
    """

    def test_setup_token_returns_200_without_auth(self):
        """Setup-token reachable without X-Auth-Token (intentional Zero-Config seam)."""
        client, _ = _make_client()
        resp = client.get("/api/v1/auth/setup-token")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}"

    def test_setup_token_returns_structured_ok_token_source(self):
        """Setup-token returns {ok, token, source} contract."""
        client, _ = _make_client()
        resp = client.get("/api/v1/auth/setup-token")
        data = resp.get_json()
        assert "ok" in data
        assert "token" in data
        assert "source" in data
        assert data["source"] in ("auto", "options", "env", "none")

    def test_setup_token_does_not_require_x_auth_header(self):
        """Contract: no X-Auth-Token must not return 401 on /setup-token."""
        client, _ = _make_client()
        resp = client.get("/api/v1/auth/setup-token")
        assert resp.status_code != 401, "/setup-token must not require auth"


# ── Test: security/token status endpoints ─────────────────────────────────────

@pytest.mark.skip(reason="H4-flaky-005: full-suite env context pollution — passes in isolation")
class TestSecurityStatusEndpoints:
    """P0-001 Audit: security and token status endpoints require auth."""

    def test_security_status_requires_auth(self):
        """GET /api/v1/security/status returns 401 without token."""
        client, _ = _make_client()
        resp = client.get("/api/v1/security/status")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_token_status_requires_auth(self):
        """GET /api/v1/security/token/status returns 401 without token."""
        client, _ = _make_client()
        resp = client.get("/api/v1/security/token/status")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_security_status_with_valid_token_returns_200(self):
        """GET /api/v1/security/status with valid token returns 200."""
        os.environ["COPILOT_AUTH_TOKEN"] = "pilotclaw-test-token"
        client, headers = _make_client(token="pilotclaw-test-token")
        resp = client.get("/api/v1/security/status", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}"

    def test_token_status_with_valid_token_returns_200(self):
        """GET /api/v1/security/token/status with valid token returns 200."""
        os.environ["COPILOT_AUTH_TOKEN"] = "pilotclaw-test-token"
        client, headers = _make_client(token="pilotclaw-test-token")
        resp = client.get("/api/v1/security/token/status", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}"

    def test_token_status_never_exposes_raw_token(self):
        """Token status response must not contain the raw token value.

        Uses a known test token and verifies the response body contains
        no substring matching the token (case-insensitive check).
        """
        test_token = "pilotclaw-test-token-secret-xyz"
        os.environ["COPILOT_AUTH_TOKEN"] = test_token
        # Force-reload the token getter so the new env value is picked up
        import importlib
        import copilot_core.api.security as sec_module
        importlib.reload(sec_module)
        client, headers = _make_client(token=test_token)
        resp = client.get("/api/v1/security/token/status", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.get_json()
        response_str = str(data).lower()
        assert test_token.lower() not in response_str, \
            f"Raw token must never appear in response body"

    def test_protected_endpoint_rejects_invalid_token(self):
        """Protected endpoint returns 401 when given wrong token."""
        client, _ = _make_client()
        headers = {"X-Auth-Token": "pilotclaw-WRONG-token"}
        resp = client.get("/api/v1/security/status", headers=headers)
        assert resp.status_code in (401, 403), \
            f"Invalid token must be rejected, got {resp.status_code}"

    def test_protected_endpoint_rejects_tampered_bearer(self):
        """Bearer auth with wrong token returns 401."""
        client, _ = _make_client()
        headers = {"Authorization": "Bearer pilotclaw-WRONGTAMpered"}
        resp = client.get("/api/v1/security/status", headers=headers)
        assert resp.status_code in (401, 403), \
            f"Tampered bearer must be rejected, got {resp.status_code}"
