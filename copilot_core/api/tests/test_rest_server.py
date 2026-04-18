"""REST API Server Tests — Comprehensive test suite for FastAPI server."""
from __future__ import annotations

import pytest
import time
from typing import Dict, Any

from copilot_core.api.voice_discovery import voice_capabilities_module


class TestRESTAPIServer:
    """Test REST API server endpoints."""

    @pytest.fixture
    def api_client(self):
        """Create test API client."""
        TestClient = pytest.importorskip(
            "fastapi.testclient",
            reason="fastapi not installed in smoke-gate environment",
        ).TestClient
        from copilot_core.api.rest_server import create_app, APIConfig
        
        config = APIConfig(debug=True, host="127.0.0.1", port=8080)
        app = create_app(config)
        client = TestClient(app)
        yield client

    def test_health_check(self, api_client):
        """Test health check endpoint."""
        response = api_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data

    def test_version(self, api_client):
        """Test version endpoint."""
        response = api_client.get("/version")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0-rc2"
        assert "build" in data
        assert data["fastapi"] is True

    def test_status(self, api_client):
        """Test system status endpoint."""
        response = api_client.get("/api/v1/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "modules" in data
        assert "capabilities" in data

    def test_health_exposes_runtime_persistence_truth(self, api_client, monkeypatch, tmp_path):
        """Repo-root health surface should expose runtime persistence truth."""
        from copilot_core.api import rest_server

        conversation_db_path = tmp_path / "memory" / "rest-health-conversation.db"
        vector_db_path = tmp_path / "vector" / "rest-health-store.db"
        shopping_db_path = tmp_path / "shopping" / "rest-health-shopping.db"
        monkeypatch.setenv("CONVERSATION_MEMORY_DB", str(conversation_db_path))
        monkeypatch.setenv("COPILOT_VECTOR_DB_PATH", str(vector_db_path))
        monkeypatch.setenv("SHOPPING_DB_PATH", str(shopping_db_path))
        monkeypatch.setattr(
            rest_server.os.path,
            "exists",
            lambda path: path in {str(conversation_db_path), str(shopping_db_path)},
        )

        response = api_client.get("/health")

        assert response.status_code == 200
        assert response.json()["persistence"] == {
            "conversation_memory_db_path": str(conversation_db_path),
            "conversation_memory_db_accessible": True,
            "vector_store_db_path": str(vector_db_path),
            "vector_store_db_accessible": False,
            "shopping_db_path": str(shopping_db_path),
            "shopping_db_accessible": True,
        }

    def test_status_exposes_runtime_persistence_truth(self, api_client, monkeypatch, tmp_path):
        """Repo-root status surface should expose runtime persistence truth."""
        from copilot_core.api import rest_server

        conversation_db_path = tmp_path / "memory" / "rest-status-conversation.db"
        vector_db_path = tmp_path / "vector" / "rest-status-store.db"
        shopping_db_path = tmp_path / "shopping" / "rest-status-shopping.db"
        monkeypatch.setenv("CONVERSATION_MEMORY_DB", str(conversation_db_path))
        monkeypatch.setenv("COPILOT_VECTOR_DB_PATH", str(vector_db_path))
        monkeypatch.setenv("SHOPPING_DB_PATH", str(shopping_db_path))
        monkeypatch.setattr(
            rest_server.os.path,
            "exists",
            lambda path: path in {str(vector_db_path), str(shopping_db_path)},
        )

        response = api_client.get("/api/v1/status")

        assert response.status_code == 200
        assert response.json()["persistence"] == {
            "conversation_memory_db_path": str(conversation_db_path),
            "conversation_memory_db_accessible": False,
            "vector_store_db_path": str(vector_db_path),
            "vector_store_db_accessible": True,
            "shopping_db_path": str(shopping_db_path),
            "shopping_db_accessible": True,
        }

    def test_capabilities_requires_auth(self, api_client):
        """Capabilities endpoint stays auth-gated like the Flask runtime surface."""
        response = api_client.get("/api/v1/capabilities")

        assert response.status_code == 401

    def test_capabilities(self, api_client):
        """Test capabilities endpoint."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        token = token_response.json()["access_token"]

        response = api_client.get(
            "/api/v1/capabilities",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "modules" in data
        assert isinstance(data["modules"], dict)
        assert data["modules"]["voice"] == voice_capabilities_module()
        assert "voice_context" not in data["modules"]
        assert data["modules"]["rag"] == ["embedding", "similarity_search", "retrieval"]

    def test_create_token(self, api_client):
        """Test token creation."""
        response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["scope"] == "read"

    def test_create_token_invalid_key(self, api_client):
        """Test token creation with invalid key."""
        response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "x", "scope": "read"}  # Too short
        )
        
        assert response.status_code == 401

    def test_authenticated_request(self, api_client):
        """Test authenticated request."""
        # Get token first
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        token = token_response.json()["access_token"]
        
        # Make authenticated request
        response = api_client.get(
            "/api/v1/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200

    def test_unauthenticated_request(self, api_client):
        """Test unauthenticated request to protected endpoint."""
        response = api_client.get("/api/v1/events")
        
        assert response.status_code == 401

    def test_events_get(self, api_client):
        """Test GET events endpoint."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        token = token_response.json()["access_token"]
        
        response = api_client.get(
            "/api/v1/events",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert data["limit"] == 10

    def test_events_post(self, api_client):
        """Test POST event endpoint."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "write"}
        )
        token = token_response.json()["access_token"]
        
        response = api_client.post(
            "/api/v1/events",
            headers={"Authorization": f"Bearer {token}"},
            json={"type": "test_event", "entity_id": "sensor.test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert "event_id" in data

    def test_events_batch(self, api_client):
        """Test batch event ingestion."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "write"}
        )
        token = token_response.json()["access_token"]
        
        events = [{"type": "test", "id": i} for i in range(5)]
        
        response = api_client.post(
            "/api/v1/events/batch",
            headers={"Authorization": f"Bearer {token}"},
            json={"events": events}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 5

    def test_vector_stats(self, api_client):
        """Test vector stats endpoint."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        token = token_response.json()["access_token"]
        
        response = api_client.get(
            "/api/v1/vector/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "vector_count" in data
        assert "dimension" in data

    def test_graph_stats(self, api_client):
        """Test graph stats endpoint."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        token = token_response.json()["access_token"]
        
        response = api_client.get(
            "/api/v1/graph/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "node_count" in data
        assert "edge_count" in data

    def test_mood_state(self, api_client):
        """Test mood state endpoint."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        token = token_response.json()["access_token"]
        
        response = api_client.get(
            "/api/v1/mood/state",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "mood" in data
        assert "score" in data

    def test_search(self, api_client):
        """Test search endpoint."""
        token_response = api_client.post(
            "/api/v1/auth/token",
            json={"api_key": "test_api_key_12345", "scope": "read"}
        )
        token = token_response.json()["access_token"]
        
        response = api_client.get(
            "/api/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": "test query", "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["query"] == "test query"

    def test_rate_limiting(self, api_client):
        """Test rate limiting."""
        # Make many requests quickly
        for i in range(10):
            response = api_client.get("/health")
            assert response.status_code == 200

    def test_cors_headers(self, api_client):
        """Test CORS headers."""
        response = api_client.get("/health", headers={"Origin": "http://test.com"})
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_openapi_docs(self, api_client):
        """Test OpenAPI documentation."""
        response = api_client.get("/docs")
        assert response.status_code == 200
        
        response = api_client.get("/redoc")
        assert response.status_code == 200
        
        response = api_client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "PilotSuite Core API"


class TestSecurityHardening:
    """Test security hardening utilities."""

    def test_secure_token_generation(self):
        """Test secure token generation."""
        from copilot_core.security.hardening import SecureTokenGenerator
        
        gen = SecureTokenGenerator()
        token = gen.generate()
        
        assert len(token) >= 44  # 32 bytes base64
        assert gen.verify_token(token) is True

    def test_api_key_generation(self):
        """Test API key generation."""
        from copilot_core.security.hardening import SecureTokenGenerator
        
        gen = SecureTokenGenerator()
        api_key = gen.generate_api_key()
        
        assert api_key.startswith("sk_")
        assert len(api_key) >= 47  # prefix + 32 bytes base64

    def test_password_hashing(self):
        """Test password hashing."""
        from copilot_core.security.hardening import PasswordHasher
        
        hasher = PasswordHasher(iterations=1000)  # Low for testing
        result = hasher.hash("test_password")
        
        assert "salt" in result
        assert "hash" in result
        assert "iterations" in result
        
        # Verify
        assert hasher.verify("test_password", result["salt"], result["hash"]) is True
        assert hasher.verify("wrong_password", result["salt"], result["hash"]) is False

    def test_encryption_at_rest(self):
        """Test encryption at rest."""
        from copilot_core.security.hardening import EncryptionAtRest
        
        enc = EncryptionAtRest()
        data = {"secret": "value", "number": 42}
        
        encrypted = enc.encrypt_json(data)
        decrypted = enc.decrypt_json(encrypted)
        
        assert decrypted == data

    def test_api_key_store(self):
        """Test API key store."""
        from copilot_core.security.hardening import APIKeyStore
        import os
        
        store = APIKeyStore(os.urandom(32))
        api_key = "sk_test_key_123456789012345678901234567890"
        
        # Add key
        key_hash = store.add_key(api_key, scope="read", expires_in_hours=24)
        
        assert key_hash is not None
        
        # Verify key
        metadata = store.verify_key(api_key)
        
        assert metadata is not None
        assert metadata["scope"] == "read"
        assert metadata["usage_count"] == 1
        
        # Revoke key
        assert store.revoke_key(api_key) is True
        assert store.verify_key(api_key) is None


# Run with: pytest copilot_core/api/tests/test_rest_server.py -v
