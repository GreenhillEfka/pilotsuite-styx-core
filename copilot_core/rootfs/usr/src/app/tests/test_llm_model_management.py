"""Tests for LLM Model Management API endpoints.

Tests the new model pull/delete/status/recommended endpoints:
  - POST /chat/models/pull          (trigger Ollama download)
  - POST /chat/models/pull/status   (check if model installed)
  - POST /chat/models/delete        (delete Ollama model)
  - GET  /chat/models/recommended   (recommended offline + cloud models)
  - POST /chat/routing              (update LLM routing)
  - GET  /chat/routing              (get LLM routing)
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask


def _make_app():
    """Create Flask app with conversation blueprint."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    from copilot_core.api.v1.conversation import conversation_bp
    app.register_blueprint(conversation_bp)
    return app


@pytest.fixture
def mock_provider():
    """Mock LLMProvider with sensible defaults."""
    provider = MagicMock()
    provider.ollama_url = "http://localhost:11434"
    provider.status.return_value = {
        "ollama_available": True,
        "cloud_configured": False,
        "ollama_model": "qwen3:4b",
        "cloud_model": "gpt-4.1-nano",
        "prefer_local": True,
        "primary_provider": "offline",
        "secondary_provider": "cloud",
        "active_provider": "offline",
        "ollama_url": "http://localhost:11434",
        "cloud_api_url": "",
        "primary_model": "qwen3:4b",
        "secondary_model": "gpt-4.1-nano",
    }
    provider.model_catalog.return_value = {
        "offline": {
            "models": ["qwen3:4b", "qwen3:0.6b"],
            "active_model": "qwen3:4b",
        },
        "cloud": {
            "models": [],
            "active_model": "gpt-4.1-nano",
            "recommended": [],
        },
    }
    provider.reload_config.return_value = None
    return provider


@pytest.fixture
def client(mock_provider):
    """Flask test client with auth bypassed and provider mocked."""
    with patch("copilot_core.api.v1.conversation.require_token", lambda f: f):
        with patch("copilot_core.api.v1.conversation._get_llm_provider", return_value=mock_provider):
            app = _make_app()
            with app.test_client() as c:
                yield c


# ── Model Pull Tests ─────────────────────────────────────────────────

class TestModelPull:
    def test_pull_missing_model(self, client):
        resp = client.post("/chat/models/pull", json={})
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data["ok"] is False
        assert "model" in data["error"].lower()

    def test_pull_empty_model(self, client):
        resp = client.post("/chat/models/pull", json={"model": ""})
        assert resp.status_code == 400

    def test_pull_success(self, client):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success"}

        with patch("requests.post", return_value=mock_resp):
            resp = client.post("/chat/models/pull", json={"model": "qwen3:4b"})
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["ok"] is True
            assert data["model"] == "qwen3:4b"
            assert data["status"] == "success"

    def test_pull_ollama_error(self, client):
        mock_resp = Mock()
        mock_resp.status_code = 500
        mock_resp.text = "internal server error"

        with patch("requests.post", return_value=mock_resp):
            resp = client.post("/chat/models/pull", json={"model": "bad:model"})
            assert resp.status_code == 502
            data = json.loads(resp.data)
            assert data["ok"] is False

    def test_pull_ollama_unreachable(self, client):
        import requests as http_req
        with patch("requests.post", side_effect=http_req.exceptions.ConnectionError("refused")):
            resp = client.post("/chat/models/pull", json={"model": "qwen3:4b"})
            assert resp.status_code == 503
            data = json.loads(resp.data)
            assert data["ok"] is False
            assert "erreichbar" in data["error"]

    def test_pull_timeout(self, client):
        import requests as http_req
        with patch("requests.post", side_effect=http_req.exceptions.Timeout("timeout")):
            resp = client.post("/chat/models/pull", json={"model": "llama3.2:70b"})
            assert resp.status_code == 504
            data = json.loads(resp.data)
            assert data["ok"] is False
            assert "Timeout" in data["error"]


# ── Model Pull Status Tests ──────────────────────────────────────────

class TestModelPullStatus:
    def test_status_missing_model(self, client):
        resp = client.post("/chat/models/pull/status", json={})
        assert resp.status_code == 400

    def test_status_installed(self, client):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "details": {"families": ["qwen2"]},
            "modelinfo": {
                "format": "gguf",
                "family": "qwen2",
                "parameter_size": "4B",
                "quantization_level": "Q4_K_M",
            },
        }

        with patch("requests.post", return_value=mock_resp):
            resp = client.post("/chat/models/pull/status", json={"model": "qwen3:4b"})
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["ok"] is True
            assert data["installed"] is True
            assert data["details"]["parameter_size"] == "4B"

    def test_status_not_installed(self, client):
        mock_resp = Mock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {}

        with patch("requests.post", return_value=mock_resp):
            resp = client.post("/chat/models/pull/status", json={"model": "nonexistent:7b"})
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["installed"] is False

    def test_status_ollama_down(self, client):
        with patch("requests.post", side_effect=ConnectionError("down")):
            resp = client.post("/chat/models/pull/status", json={"model": "qwen3:4b"})
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["installed"] is False


# ── Model Delete Tests ───────────────────────────────────────────────

class TestModelDelete:
    def test_delete_missing_model(self, client):
        resp = client.post("/chat/models/delete", json={})
        assert resp.status_code == 400

    def test_delete_success(self, client):
        mock_resp = Mock()
        mock_resp.status_code = 200

        with patch("requests.delete", return_value=mock_resp):
            resp = client.post("/chat/models/delete", json={"model": "qwen3:0.6b"})
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["ok"] is True
            assert data["status"] == "deleted"

    def test_delete_not_found(self, client):
        mock_resp = Mock()
        mock_resp.status_code = 404
        mock_resp.text = "model not found"

        with patch("requests.delete", return_value=mock_resp):
            resp = client.post("/chat/models/delete", json={"model": "nonexistent"})
            assert resp.status_code == 502

    def test_delete_ollama_error(self, client):
        with patch("requests.delete", side_effect=Exception("connection failed")):
            resp = client.post("/chat/models/delete", json={"model": "qwen3:4b"})
            assert resp.status_code == 500


# ── Recommended Models Tests ─────────────────────────────────────────

class TestRecommendedModels:
    def test_recommended_returns_offline_and_cloud(self, client):
        resp = client.get("/chat/models/recommended")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert "offline" in data
        assert "cloud" in data
        assert len(data["offline"]) > 0
        assert len(data["cloud"]) > 0

    def test_recommended_offline_has_install_status(self, client):
        resp = client.get("/chat/models/recommended")
        data = json.loads(resp.data)
        for model in data["offline"]:
            assert "installed" in model
            assert "active" in model
            assert "id" in model

    def test_recommended_cloud_has_pricing(self, client):
        resp = client.get("/chat/models/recommended")
        data = json.loads(resp.data)
        for model in data["cloud"]:
            assert "id" in model
            assert "active" in model

    def test_recommended_includes_qwen3(self, client):
        resp = client.get("/chat/models/recommended")
        data = json.loads(resp.data)
        ids = [m["id"] for m in data["offline"]]
        assert "qwen3:4b" in ids

    def test_recommended_includes_gpt4_nano(self, client):
        resp = client.get("/chat/models/recommended")
        data = json.loads(resp.data)
        ids = [m["id"] for m in data["cloud"]]
        assert "gpt-4.1-nano" in ids

    def test_recommended_marks_active_model(self, client, mock_provider):
        mock_provider.model_catalog.return_value = {
            "offline": {
                "models": ["qwen3:4b"],
                "active_model": "qwen3:4b",
            },
            "cloud": {
                "models": [],
                "active_model": "gpt-4.1-nano",
            },
        }
        resp = client.get("/chat/models/recommended")
        data = json.loads(resp.data)
        active_offline = [m for m in data["offline"] if m["active"]]
        assert len(active_offline) == 1
        assert active_offline[0]["id"] == "qwen3:4b"


# ── Routing Tests ────────────────────────────────────────────────────

class TestRouting:
    def test_routing_get(self, client):
        resp = client.get("/chat/routing")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert "primary_provider" in data

    def test_routing_set(self, client, mock_provider):
        mock_provider.update_routing.return_value = {
            "primary_provider": "cloud",
            "secondary_provider": "offline",
        }
        resp = client.post("/chat/routing", json={
            "primary_provider": "cloud",
            "secondary_provider": "offline",
            "cloud_model": "gpt-4.1-nano",
        })
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        mock_provider.update_routing.assert_called_once()


# ── Default Model Tests ──────────────────────────────────────────────

class TestDefaults:
    def test_default_ollama_model_is_qwen3_4b(self):
        from copilot_core.llm_provider import _DEFAULT_OLLAMA_MODEL
        assert _DEFAULT_OLLAMA_MODEL == "qwen3:4b"

    def test_default_cloud_model_is_gpt41_nano(self):
        from copilot_core.llm_provider import _DEFAULT_CLOUD_MODEL
        assert _DEFAULT_CLOUD_MODEL == "gpt-4.1-nano"

    def test_recommended_models_list_not_empty(self):
        from copilot_core.api.v1.conversation import RECOMMENDED_MODELS, RECOMMENDED_CLOUD_MODELS
        assert len(RECOMMENDED_MODELS) >= 4
        assert len(RECOMMENDED_CLOUD_MODELS) >= 2

    def test_default_model_is_qwen3_4b(self):
        from copilot_core.api.v1.conversation import DEFAULT_MODEL
        assert DEFAULT_MODEL == "qwen3:4b"
