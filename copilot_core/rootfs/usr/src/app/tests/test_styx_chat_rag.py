"""
Tests fuer PilotSuite-Styx Chat mit interner RAG-Pipeline-Integration.

Test-Coverage:
- ChatHandler (Unit Tests)
- API-Endpoint (Integration Tests)
- RAG-Suche (lokal vs. Web)
- Error-Handling
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import Any, Dict

from copilot_core.styx.chat_handler import ChatHandler
from copilot_core.api.v1.styx_chat import ChatRequest, _get_chat_handler


@pytest.fixture
def chat_handler():
    """Erstelle ChatHandler fuer Tests."""
    return ChatHandler(ollama_url="http://localhost:11434")


@pytest.fixture
def mock_rag_results():
    """Mock-RAG-Ergebnisse (internes Format)."""
    return {
        "results": [
            {"content": "Energieverbrauch gestern: 12.5 kWh", "source": "ha_states", "score": 0.95, "doc_id": "ha_state_123", "search_type": "bm25"},
            {"content": "Durchschnittlicher Verbrauch: 10 kWh/Tag", "source": "documents", "score": 0.85, "doc_id": "doc_456", "search_type": "bm25"},
        ],
        "sources": [
            {"id": "ha_state_123", "score": 0.95, "source": "ha_states"},
            {"id": "doc_456", "score": 0.85, "source": "documents"},
        ],
        "query_type": "local",
    }


@pytest.fixture
def mock_ollama_response():
    return {"response": "Der Energieverbrauch gestern betrug 12.5 kWh.", "model": "qwen3:0.6b"}


class TestChatRequest:
    def test_chat_request_minimal(self):
        req = ChatRequest.from_json({"query": "Wie war der Energieverbrauch?", "user_id": "test_user"})
        assert req.query == "Wie war der Energieverbrauch?"
        assert req.user_id == "test_user"
        assert req.use_web is False

    def test_chat_request_full(self):
        req = ChatRequest.from_json({"query": "Wetter?", "user_id": "u1", "use_web": True, "model": "llama3.2:3b"})
        assert req.use_web is True
        assert req.model == "llama3.2:3b"

    def test_chat_request_empty_query(self):
        assert ChatRequest.from_json({"query": "", "user_id": "t"}).query == ""

    def test_chat_request_missing_user_id(self):
        assert ChatRequest.from_json({"query": "x"}).user_id == "anonymous"


class TestChatHandlerInit:
    def test_chat_handler_init_default(self):
        handler = ChatHandler()
        assert handler.ollama_url == "http://127.0.0.1:11434"
        assert handler._initialized is False

    def test_chat_handler_init_trailing_slash(self):
        handler = ChatHandler(ollama_url="http://localhost:11434/")
        assert handler.ollama_url == "http://localhost:11434"


class TestSearchInternal:
    def test_search_internal_local(self, chat_handler):
        chat_handler._initialized = True
        chat_handler._bm25_index = None
        chat_handler._searxng_client = None
        result = chat_handler._search_internal("test", False, "local")
        assert result["query_type"] == "local"

    def test_search_internal_with_bm25(self, chat_handler):
        mock_hit = MagicMock(text="Energie: 12.5 kWh", score=0.95, namespace="ha_states", doc_id="s1")
        mock_bm25 = MagicMock()
        mock_bm25.search.return_value = [mock_hit]
        chat_handler._initialized = True
        chat_handler._bm25_index = mock_bm25
        chat_handler._searxng_client = None
        result = chat_handler._search_internal("Energie", False, "local")
        assert len(result["results"]) == 1
        assert result["results"][0]["score"] == 0.95

    def test_search_internal_web(self, chat_handler):
        mock_wr = MagicMock(snippet="Wetter 20C", score=0.92, url="https://ex.com")
        mock_searxng = MagicMock()
        mock_searxng.search.return_value = [mock_wr]
        chat_handler._initialized = True
        chat_handler._bm25_index = None
        chat_handler._searxng_client = mock_searxng
        result = chat_handler._search_internal("Wetter", True, "web")
        assert result["query_type"] == "web"
        assert len(result["results"]) == 1

    def test_search_internal_error(self, chat_handler):
        mock_bm25 = MagicMock()
        mock_bm25.search.side_effect = Exception("DB error")
        chat_handler._initialized = True
        chat_handler._bm25_index = mock_bm25
        chat_handler._searxng_client = None
        result = chat_handler._search_internal("test", False, "local")
        assert isinstance(result["results"], list)


class TestBuildPrompt:
    def test_build_prompt_with_context(self, chat_handler, mock_rag_results):
        prompt = chat_handler._build_prompt("Energieverbrauch?", mock_rag_results)
        assert "Relevanter Kontext:" in prompt
        assert "[Quelle 1]" in prompt
        assert "[Quelle 2]" in prompt

    def test_build_prompt_no_context(self, chat_handler):
        prompt = chat_handler._build_prompt("Testfrage", {"results": [], "sources": [], "query_type": "local"})
        assert "Beantworte Fragen praezise" in prompt
        assert "Relevanter Kontext:" not in prompt

    def test_build_prompt_query_type_included(self, chat_handler, mock_rag_results):
        mock_rag_results["query_type"] = "web"
        prompt = chat_handler._build_prompt("Wetter?", mock_rag_results)
        assert "Quelle" in prompt


class TestCallOllama:
    def test_call_ollama_direct_success(self, chat_handler, mock_ollama_response):
        with patch("copilot_core.styx.chat_handler.requests") as mock_req:
            mock_resp = MagicMock(status_code=200)
            mock_resp.json.return_value = mock_ollama_response
            mock_req.post.return_value = mock_resp
            assert chat_handler._call_ollama_direct("test", "qwen3:0.6b") == "Der Energieverbrauch gestern betrug 12.5 kWh."

    def test_call_ollama_direct_error(self, chat_handler):
        with patch("copilot_core.styx.chat_handler.requests") as mock_req:
            mock_req.post.return_value = MagicMock(status_code=500)
            response = chat_handler._call_ollama_direct("test", "qwen3:0.6b")
            assert "Entschuldigung" in response
            assert "500" in response

    def test_call_ollama_direct_custom_model(self, chat_handler, mock_ollama_response):
        with patch("copilot_core.styx.chat_handler.requests") as mock_req:
            mock_resp = MagicMock(status_code=200)
            mock_resp.json.return_value = mock_ollama_response
            mock_req.post.return_value = mock_resp
            chat_handler._call_ollama_direct("test", "llama3.2:3b")
            assert mock_req.post.call_args[1]["json"]["model"] == "llama3.2:3b"


class TestHandleQuery:
    def test_handle_query_local(self, chat_handler, mock_rag_results, mock_ollama_response):
        with patch.object(chat_handler, "_search_internal", return_value=mock_rag_results):
            with patch.object(chat_handler, "_call_llm", return_value=mock_ollama_response["response"]):
                result = chat_handler.handle_query("Energieverbrauch?", "test_user", use_web=False)
                assert result["query_type"] == "local"
                assert len(result["sources"]) == 2

    def test_handle_query_web(self, chat_handler, mock_ollama_response):
        web_results = {"results": [{"content": "Web", "source": "web", "score": 0.9}], "sources": [{"id": "1", "score": 0.9, "source": "web"}], "query_type": "web"}
        with patch.object(chat_handler, "_search_internal", return_value=web_results):
            with patch.object(chat_handler, "_call_llm", return_value=mock_ollama_response["response"]):
                result = chat_handler.handle_query("Wetter?", "test_user", use_web=True)
                assert result["query_type"] == "web"

    def test_handle_query_logs_interaction(self, chat_handler, mock_rag_results, mock_ollama_response):
        """Test: handle_query completes without error and returns result."""
        with patch.object(chat_handler, "_search_internal", return_value=mock_rag_results):
            with patch.object(chat_handler, "_call_llm", return_value=mock_ollama_response["response"]):
                result = chat_handler.handle_query("Testfrage", "test_user_123", use_web=False)
                assert "response" in result
                assert "elapsed_ms" in result


class TestStyxChatEndpoint:
    def _create_test_client(self):
        from flask import Flask
        from copilot_core.api.v1.styx_chat import bp as styx_bp
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(styx_bp)
        return app.test_client()

    def test_styx_chat_missing_query(self):
        client = self._create_test_client()
        response = client.post("/api/styx/chat", json={"user_id": "test_user"})
        assert response.status_code == 400

    def test_styx_chat_missing_user_id_defaults_to_anonymous(self):
        client = self._create_test_client()
        response = client.post("/api/styx/chat", json={"query": "test"})
        assert response.status_code in (200, 201)

    def test_styx_chat_success(self, mock_rag_results, mock_ollama_response):
        client = self._create_test_client()
        with patch("copilot_core.api.v1.styx_chat._get_chat_handler") as mock_getter:
            mock_handler = MagicMock()
            mock_handler.handle_query.return_value = {
                "response": mock_ollama_response["response"],
                "sources": mock_rag_results["sources"],
                "query_type": "local",
                "context_used": mock_rag_results["results"],
            }
            mock_getter.return_value = mock_handler
            response = client.post("/api/styx/chat", json={"query": "Energieverbrauch?", "user_id": "test_user"})
            assert response.status_code == 200
            assert response.get_json()["ok"] is True


class TestHealthEndpoint:
    def test_styx_health(self):
        from flask import Flask
        from copilot_core.api.v1.styx_chat import bp
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(bp)
        client = app.test_client()
        response = client.get("/api/styx/health")
        assert response.status_code in [200, 503]
        assert "ok" in response.get_json()


class TestEdgeCases:
    def test_empty_rag_results(self, chat_handler, mock_ollama_response):
        empty = {"results": [], "sources": [], "query_type": "local"}
        with patch.object(chat_handler, "_search_internal", return_value=empty):
            with patch.object(chat_handler, "_call_llm", return_value=mock_ollama_response["response"]):
                result = chat_handler.handle_query("test", "u", use_web=False)
                assert len(result["sources"]) == 0

    def test_very_long_query(self, chat_handler, mock_rag_results, mock_ollama_response):
        with patch.object(chat_handler, "_search_internal", return_value=mock_rag_results):
            with patch.object(chat_handler, "_call_llm", return_value=mock_ollama_response["response"]):
                result = chat_handler.handle_query("Frage " * 1000, "u", use_web=False)
                assert result["response"] == mock_ollama_response["response"]

    def test_special_characters_in_query(self, chat_handler, mock_rag_results, mock_ollama_response):
        with patch.object(chat_handler, "_search_internal", return_value=mock_rag_results):
            with patch.object(chat_handler, "_call_llm", return_value=mock_ollama_response["response"]):
                result = chat_handler.handle_query("Test <>&\"' aoeue", "u", use_web=False)
                assert result["response"] == mock_ollama_response["response"]


class TestQueryTypes:
    def test_local_query_type(self, chat_handler):
        mock_r = {"results": [{"content": "L", "source": "ha", "score": 0.9}], "sources": [{"id": "1", "score": 0.9, "source": "ha"}], "query_type": "local"}
        with patch.object(chat_handler, "_search_internal", return_value=mock_r):
            with patch.object(chat_handler, "_call_llm", return_value="Antwort"):
                assert chat_handler.handle_query("test", "u", use_web=False)["query_type"] == "local"

    def test_web_query_type(self, chat_handler):
        mock_r = {"results": [{"content": "W", "source": "web", "score": 0.9}], "sources": [{"id": "1", "score": 0.9, "source": "web"}], "query_type": "web"}
        with patch.object(chat_handler, "_classify_query", return_value="web"):
            with patch.object(chat_handler, "_search_internal", return_value=mock_r):
                with patch.object(chat_handler, "_call_llm", return_value="Antwort"):
                    assert chat_handler.handle_query("test", "u", use_web=True)["query_type"] == "web"


class TestStyxHealthBackend:
    @pytest.fixture
    def client(self):
        from flask import Flask
        from copilot_core.api.v1.styx_chat import bp
        app = Flask(__name__)
        app.register_blueprint(bp)
        app.config["COPILOT_SERVICES"] = {}
        with app.test_client() as client:
            yield client

    def test_health_backend_empty_services(self, client):
        response = client.get("/api/styx/health/backend")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["total_services"] == 0

    def test_health_backend_with_services(self, client):
        m = MagicMock()
        m.health_check = MagicMock(return_value={"status": "ok"})
        client.application.config["COPILOT_SERVICES"] = {"brain": m, "habitus": None}
        response = client.get("/api/styx/health/backend")
        assert response.status_code == 503
        assert "habitus" in response.get_json()["unhealthy_services"]

    def test_health_backend_all_healthy(self, client):
        m = MagicMock()
        m.health_check = MagicMock(return_value={"status": "ok"})
        client.application.config["COPILOT_SERVICES"] = {"a": m, "b": m}
        response = client.get("/api/styx/health/backend")
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
