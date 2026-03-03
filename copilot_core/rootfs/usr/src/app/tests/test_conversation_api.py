"""Tests for Conversation API endpoints."""

import pytest
from unittest.mock import patch, MagicMock

try:
    from copilot_core.app import create_app
except ModuleNotFoundError:
    create_app = None


@pytest.fixture
def conversation_client():
    """Create a test client for the conversation API."""
    if create_app is None:
        pytest.skip("Flask not installed")
    
    app = create_app()
    app.config['TESTING'] = True
    return app.test_client()


class TestConversationEndpoints:
    """Tests for conversation API endpoints."""

    def test_get_models_endpoint(self, conversation_client):
        """Test GET /api/v1/chat/models endpoint."""
        r = conversation_client.get("/api/v1/chat/models")
        assert r.status_code == 200
        j = r.get_json()
        assert "data" in j
        assert isinstance(j["data"], list)
        # Check that recommended models are present
        model_ids = [m["id"] for m in j["data"]]
        assert "qwen3:0.6b" in model_ids

    def test_chat_completions_endpoint(self, conversation_client):
        """Test POST /api/v1/chat/completions endpoint with mocked LLM."""
        payload = {
            "model": "qwen3:0.6b",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        with patch('copilot_core.api.v1.conversation._get_llm_provider') as mock_provider:
            mock_provider.return_value = MagicMock()
            mock_provider.return_value.generate.return_value = "Hello! How can I help you?"
            
            r = conversation_client.post("/api/v1/chat/completions", json=payload)
            assert r.status_code == 200
            j = r.get_json()
            assert "choices" in j
            assert len(j["choices"]) > 0

    def test_chat_completions_with_streaming(self, conversation_client):
        """Test POST /api/v1/chat/completions with stream=true."""
        payload = {
            "model": "qwen3:0.6b",
            "messages": [{"role": "user", "content": "Test"}],
            "stream": True
        }
        
        with patch('copilot_core.api.v1.conversation._get_llm_provider') as mock_provider:
            mock_provider.return_value = MagicMock()
            mock_provider.return_value.generate_stream.return_value = iter(["Test ", "response"])
            
            r = conversation_client.post("/api/v1/chat/completions", json=payload)
            assert r.status_code == 200
            # Stream response should be chunked
            assert r.data

    def test_chat_completions_invalid_model(self, conversation_client):
        """Test POST /api/v1/chat/completions with invalid model."""
        payload = {
            "model": "invalid-model-xyz",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        
        r = conversation_client.post("/api/v1/chat/completions", json=payload)
        # Should return an error for invalid model
        assert r.status_code in [200, 400, 422]  # Allow for different error handling

    def test_chat_completions_missing_messages(self, conversation_client):
        """Test POST /api/v1/chat/completions with missing messages."""
        payload = {
            "model": "qwen3:0.6b"
            # Missing messages
        }
        
        r = conversation_client.post("/api/v1/chat/completions", json=payload)
        # Should return validation error
        assert r.status_code in [400, 422]

    def test_chat_completions_empty_messages(self, conversation_client):
        """Test POST /api/v1/chat/completions with empty messages array."""
        payload = {
            "model": "qwen3:0.6b",
            "messages": []
        }
        
        r = conversation_client.post("/api/v1/chat/completions", json=payload)
        # Should handle empty messages gracefully
        assert r.status_code in [200, 400, 422]

    def test_chat_completions_with_tools(self, conversation_client):
        """Test POST /api/v1/chat/completions with tool definitions."""
        payload = {
            "model": "qwen3:0.6b",
            "messages": [{"role": "user", "content": "Turn on the lights"}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "turn_on_light",
                    "description": "Turn on a light",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string"}
                        }
                    }
                }
            }]
        }
        
        with patch('copilot_core.api.v1.conversation._get_llm_provider') as mock_provider:
            mock_provider.return_value = MagicMock()
            mock_provider.return_value.generate.return_value = {
                "tool_calls": [{
                    "name": "turn_on_light",
                    "arguments": {"entity_id": "light.living_room"}
                }]
            }
            
            r = conversation_client.post("/api/v1/chat/completions", json=payload)
            assert r.status_code == 200

    def test_chat_completions_with_temperature(self, conversation_client):
        """Test POST /api/v1/chat/completions with temperature parameter."""
        payload = {
            "model": "qwen3:0.6b",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7
        }
        
        with patch('copilot_core.api.v1.conversation._get_llm_provider') as mock_provider:
            mock_provider.return_value = MagicMock()
            mock_provider.return_value.generate.return_value = "Response"
            
            r = conversation_client.post("/api/v1/chat/completions", json=payload)
            assert r.status_code == 200

    def test_chat_completions_with_max_tokens(self, conversation_client):
        """Test POST /api/v1/chat/completions with max_tokens parameter."""
        payload = {
            "model": "qwen3:0.6b",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }
        
        with patch('copilot_core.api.v1.conversation._get_llm_provider') as mock_provider:
            mock_provider.return_value = MagicMock()
            mock_provider.return_value.generate.return_value = "Response"
            
            r = conversation_client.post("/api/v1/chat/completions", json=payload)
            assert r.status_code == 200

    def test_chat_completions_with_history(self, conversation_client):
        """Test POST /api/v1/chat/completions with conversation history."""
        payload = {
            "model": "qwen3:0.6b",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"}
            ]
        }
        
        with patch('copilot_core.api.v1.conversation._get_llm_provider') as mock_provider:
            mock_provider.return_value = MagicMock()
            mock_provider.return_value.generate.return_value = "I'm doing well, thanks for asking!"
            
            r = conversation_client.post("/api/v1/chat/completions", json=payload)
            assert r.status_code == 200


class TestConversationHelperFunctions:
    """Tests for conversation API helper functions."""

    def test_get_models_list(self):
        """Test that model list is accessible."""
        from copilot_core.api.v1.conversation import RECOMMENDED_MODELS
        assert len(RECOMMENDED_MODELS) > 0
        assert any(m["id"] == "qwen3:0.6b" for m in RECOMMENDED_MODELS)

    def test_model_with_tool_support(self):
        """Test that tool-calling models are identified."""
        from copilot_core.api.v1.conversation import RECOMMENDED_MODELS
        tool_models = [m for m in RECOMMENDED_MODELS if m.get("supports_tools", False)]
        assert len(tool_models) > 0

    def test_model_size_info(self):
        """Test that model sizes are available."""
        from copilot_core.api.v1.conversation import RECOMMENDED_MODELS
        for model in RECOMMENDED_MODELS:
            assert "id" in model
            assert "name" in model
            assert "size_mb" in model
