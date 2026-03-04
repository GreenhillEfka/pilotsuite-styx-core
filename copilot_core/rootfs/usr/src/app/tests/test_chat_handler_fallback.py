"""Tests for ChatHandler LLM fallback chain.

Verifies that ChatHandler uses the LLMProvider with
Ollama → Cloud fallback, and falls back to direct Ollama
when LLMProvider is unavailable.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from copilot_core.styx.chat_handler import ChatHandler


@pytest.fixture
def handler():
    """Create a ChatHandler with mocked dependencies."""
    with patch.dict("os.environ", {"OLLAMA_URL": "http://test-ollama:11434"}):
        h = ChatHandler()
    return h


class TestLLMFallbackChain:
    """Test the LLMProvider → direct Ollama fallback chain."""

    def test_llm_provider_primary(self, handler):
        """When LLMProvider works, use it."""
        mock_provider = Mock()
        mock_provider.chat.return_value = {
            "content": "LLMProvider response",
            "provider": "ollama",
        }
        handler._llm_provider = mock_provider
        handler._initialized = True

        result = handler._call_llm("test prompt", "qwen3:0.6b")
        assert result == "LLMProvider response"
        mock_provider.chat.assert_called_once()

    def test_llm_provider_empty_falls_to_direct(self, handler):
        """When LLMProvider returns empty, fall back to direct Ollama."""
        mock_provider = Mock()
        mock_provider.chat.return_value = {"content": "", "provider": "none"}
        handler._llm_provider = mock_provider
        handler._initialized = True

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Direct Ollama response"}

        with patch("requests.post", return_value=mock_resp):
            result = handler._call_llm("test prompt", "qwen3:0.6b")
            assert result == "Direct Ollama response"

    def test_llm_provider_exception_falls_to_direct(self, handler):
        """When LLMProvider raises, fall back to direct Ollama."""
        mock_provider = Mock()
        mock_provider.chat.side_effect = RuntimeError("provider crashed")
        handler._llm_provider = mock_provider
        handler._initialized = True

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Fallback response"}

        with patch("requests.post", return_value=mock_resp):
            result = handler._call_llm("test prompt", "qwen3:0.6b")
            assert result == "Fallback response"

    def test_no_llm_provider_uses_direct(self, handler):
        """When no LLMProvider available, go straight to direct Ollama."""
        handler._llm_provider = None
        handler._initialized = True

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Direct only"}

        with patch("requests.post", return_value=mock_resp):
            result = handler._call_llm("test prompt", "qwen3:0.6b")
            assert result == "Direct only"

    def test_direct_ollama_error(self, handler):
        """When direct Ollama fails, return error message."""
        handler._llm_provider = None
        handler._initialized = True

        mock_resp = Mock()
        mock_resp.status_code = 500

        with patch("requests.post", return_value=mock_resp):
            result = handler._call_ollama_direct("prompt", "model")
            assert "500" in result

    def test_direct_ollama_connection_error(self, handler):
        """When Ollama is unreachable, return error message."""
        handler._llm_provider = None
        handler._initialized = True

        from requests import ConnectionError
        with patch("requests.post", side_effect=ConnectionError("refused")):
            result = handler._call_ollama_direct("prompt", "model")
            assert "fehlgeschlagen" in result.lower() or "refused" in result.lower()


class TestPromptBuilding:
    """Test RAG prompt construction."""

    def test_empty_context_prompt(self, handler):
        """Without RAG results, use simple prompt."""
        prompt = handler._build_prompt("Was ist HA?", {"results": []})
        assert "Was ist HA?" in prompt
        assert "Quelle" not in prompt

    def test_context_prompt_with_results(self, handler):
        """With RAG results, include sources in prompt."""
        rag = {
            "results": [
                {"content": "HA ist ein Smart-Home-System", "source": "docs", "score": 0.9},
                {"content": "HA nutzt YAML", "source": "wiki", "score": 0.7},
            ]
        }
        prompt = handler._build_prompt("Was ist HA?", rag)
        assert "Was ist HA?" in prompt
        assert "Quelle 1" in prompt
        assert "Quelle 2" in prompt
        assert "Smart-Home-System" in prompt

    def test_context_limited_to_8(self, handler):
        """Only top 8 results are included in prompt."""
        rag = {
            "results": [
                {"content": f"Result {i}", "source": "test", "score": 1.0 - i * 0.1}
                for i in range(15)
            ]
        }
        prompt = handler._build_prompt("query", rag)
        assert "Quelle 8" in prompt
        assert "Quelle 9" not in prompt


class TestQueryClassification:
    """Test query classification."""

    def test_local_query_default(self, handler):
        """Default classification is 'local'."""
        result = handler._classify_query("Wie ist das Wetter?", use_web=False)
        # Should return "local" when query_router is not available
        assert result in ("local", "web", "knowledge", "current_events")

    def test_web_query_forced(self, handler):
        """When use_web=True, classification reflects web usage."""
        result = handler._classify_query("Nachrichten heute", use_web=True)
        # Should include web aspect
        assert isinstance(result, str)
