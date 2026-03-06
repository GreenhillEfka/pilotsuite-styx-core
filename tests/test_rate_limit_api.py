"""Tests for rate limit API hardening (PS-P1-007)."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import patch

from flask import Flask

from copilot_core.api.v1.rate_limit import (
    DEFAULT_RATE_LIMIT_CONFIG,
    rate_limit_bp,
)


class _RateLimitStoreSpy:
    """Simple in-memory spy for rate-limit store interactions."""

    def __init__(self, all_status: Dict[str, Dict[str, Any]] | None = None):
        self.updated_configs = []
        self.removed_clients = []
        self.cleanup_calls = []
        self.all_status = all_status or {}

    def update_config(self, client_id: str, config):
        self.updated_configs.append((client_id, config.to_dict()))

    def remove_client(self, client_id: str) -> None:
        self.removed_clients.append(client_id)

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.all_status)

    def cleanup_stale(self, max_age_seconds: int) -> int:
        self.cleanup_calls.append(max_age_seconds)
        return len(self.all_status)

    def get_config(self, client_id: str):
        return None

    def get_bucket(self, client_id: str, config):
        return None


def _build_client():
    app = Flask(__name__)
    app.register_blueprint(rate_limit_bp)
    return app.test_client()


def test_update_rate_limit_config_does_not_mutate_defaults():
    """Ensure update creates a copy of defaults instead of mutating the global object."""
    client = _build_client()
    store = _RateLimitStoreSpy()

    original_default = DEFAULT_RATE_LIMIT_CONFIG.to_dict()

    with patch(
        "copilot_core.api.security.get_auth_token", return_value="secret-token"
    ), patch("copilot_core.api.v1.rate_limit.get_rate_limit_store", return_value=store):
        response = client.put(
            "/rate-limit/config",
            json={
                "client_id": "client-alpha",
                "requests_per_minute": 500,
                "burst_size": 50,
                "algorithm": "fixed_window",
                "enabled": True,
            },
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200

        response = client.put(
            "/rate-limit/config",
            json={
                "client_id": "client-beta",
                "requests_per_minute": 200,
                "burst_size": 20,
            },
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200

    assert len(store.updated_configs) == 2
    assert store.updated_configs[0][1]["requests_per_minute"] == 500
    assert store.updated_configs[0][1]["burst_size"] == 50
    assert store.updated_configs[1][1]["requests_per_minute"] == 200
    assert store.updated_configs[1][1]["burst_size"] == 20
    assert DEFAULT_RATE_LIMIT_CONFIG.to_dict() == original_default


def test_update_rate_limit_config_bounds_validation_returns_400():
    """Validate request bounds for requests_per_minute and burst_size."""
    client = _build_client()
    store = _RateLimitStoreSpy()

    payloads = [
        {"client_id": "client-1", "requests_per_minute": 0},
        {"client_id": "client-1", "requests_per_minute": -1},
        {"client_id": "client-1", "requests_per_minute": 10001},
        {"client_id": "client-1", "burst_size": 0},
        {"client_id": "client-1", "burst_size": -1},
        {"client_id": "client-1", "burst_size": 10001},
        {"client_id": "client-1", "algorithm": "bad_algo"},
    ]

    with patch(
        "copilot_core.api.security.get_auth_token", return_value="secret-token"
    ), patch("copilot_core.api.v1.rate_limit.get_rate_limit_store", return_value=store):
        for payload in payloads:
            response = client.put(
                "/rate-limit/config",
                json=payload,
                headers={"X-Auth-Token": "secret-token"},
            )
            assert response.status_code == 400
            assert response.get_json()["error"] == "invalid_config"


def test_cleanup_rate_limit_max_age_validation_returns_400():
    """Validate max_age_seconds for cleanup: type and bounds checks."""
    client = _build_client()
    store = _RateLimitStoreSpy()

    payloads = [
        {"max_age_seconds": "invalid"},
        {"max_age_seconds": 0},
        {"max_age_seconds": -1},
        {"max_age_seconds": 604_801},
    ]

    with patch(
        "copilot_core.api.security.get_auth_token", return_value="secret-token"
    ), patch("copilot_core.api.v1.rate_limit.get_rate_limit_store", return_value=store):
        for payload in payloads:
            response = client.post(
                "/rate-limit/cleanup",
                json=payload,
                headers={"X-Auth-Token": "secret-token"},
            )
            assert response.status_code == 400
            assert response.get_json()["error"] == "invalid_config"


def test_cleanup_rate_limit_max_age_accepts_valid_boundaries():
    """Validate cleanup accepts configured boundary values."""
    client = _build_client()
    store = _RateLimitStoreSpy(all_status={"client-a": {}, "client-b": {}, "client-c": {}})

    with patch(
        "copilot_core.api.security.get_auth_token", return_value="secret-token"
    ), patch("copilot_core.api.v1.rate_limit.get_rate_limit_store", return_value=store):
        response = client.post(
            "/rate-limit/cleanup",
            json={"max_age_seconds": 1},
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200
        assert response.get_json()["max_age_seconds"] == 1
        assert response.get_json()["buckets_removed"] == len(store.all_status)

        response = client.post(
            "/rate-limit/cleanup",
            json={"max_age_seconds": 604_800},
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200
        assert response.get_json()["max_age_seconds"] == 604800

    assert store.cleanup_calls == [1, 604800]


def test_mutating_endpoints_require_admin_token_and_allow_valid_token():
    """Mutating routes must require admin auth and accept valid tokens."""
    client = _build_client()
    store = _RateLimitStoreSpy(all_status={"client-a": {}, "client-b": {}})

    with patch(
        "copilot_core.api.security.get_auth_token", return_value="secret-token"
    ), patch("copilot_core.api.v1.rate_limit.get_rate_limit_store", return_value=store):
        # PUT without token.
        response = client.put("/rate-limit/config", json={"client_id": "client-a"})
        assert response.status_code == 403

        # DELETE without token.
        response = client.delete("/rate-limit/config/client-a")
        assert response.status_code == 403

        # reset-all without token.
        response = client.post("/rate-limit/reset-all")
        assert response.status_code == 403

        # cleanup without token.
        response = client.post("/rate-limit/cleanup", json={"max_age_seconds": 3600})
        assert response.status_code == 403

        # PUT with valid token.
        response = client.put(
            "/rate-limit/config",
            json={"client_id": "client-a", "requests_per_minute": 250, "burst_size": 30},
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200

        # DELETE with valid token.
        response = client.delete(
            "/rate-limit/config/client-a",
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200

        # reset-all with valid token.
        response = client.post(
            "/rate-limit/reset-all",
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200
        assert response.get_json()["clients_cleared"] == 2

        # cleanup with valid token.
        response = client.post(
            "/rate-limit/cleanup",
            json={"max_age_seconds": 900},
            headers={"X-Auth-Token": "secret-token"},
        )
        assert response.status_code == 200
        assert response.get_json()["buckets_removed"] == len(store.all_status)

    assert store.cleanup_calls == [900]
