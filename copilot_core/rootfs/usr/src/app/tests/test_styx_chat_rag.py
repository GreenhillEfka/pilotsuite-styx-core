"""
Tests für PilotSuite-Styx Chat mit RAG-API Integration.

Test-Coverage:
- ChatHandler (Unit Tests)
- API-Endpoint (Integration Tests)
- RAG-Suche (lokal vs. Web)
- History-Logging
- Error-Handling
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import Any, Dict

# Import zu testende Komponenten
from copilot_core.styx.chat_handler import ChatHandler
from copilot_core.api.v1.styx_chat import ChatRequest, _get_chat_handler


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def chat_handler():
    """Erstelle ChatHandler für Tests."""
    return ChatHandler(
        rag_api_url="http://localhost:8765",
        ollama_url="http://localhost:11434",
    )


@pytest.fixture
def mock_rag_response():
    """Mock-RAG-Antwort für Tests."""
    return {
        "results": [
            {
                "id": "ha_state_123",
                "content": "Energieverbrauch gestern: 12.5 kWh",
                "source": "ha_states",
                "score": 0.95,
            },
            {
                "id": "doc_456",
                "content": "Durchschnittlicher Verbrauch: 10 kWh/Tag",
                "source": "documents",
                "score": 0.85,
            },
        ],
        "sources": [
            {"id": "ha_state_123", "score": 0.95, "source": "ha_states"},
            {"id": "doc_456", "score": 0.85, "source": "documents"},
        ],
        "query_type": "local",
    }


@pytest.fixture
def mock_ollama_response():
    """Mock-Ollama-Antwort für Tests."""
    return {
        "response": "Der Energieverbrauch gestern betrug 12.5 kWh.",
        "model": "qwen3.5:397b-cloud",
    }


# ══════════════════════════════════════════════════════════════════════════
# Test: ChatRequest Schema
# ══════════════════════════════════════════════════════════════════════════

class TestChatRequest:
    """Tests für ChatRequest Schema."""
    
    def test_chat_request_minimal(self):
        """Test: Minimale Request (nur required fields)."""
        data = {
            "query": "Wie war der Energieverbrauch?",
            "user_id": "test_user",
        }
        req = ChatRequest.from_json(data)
        
        assert req.query == "Wie war der Energieverbrauch?"
        assert req.user_id == "test_user"
        assert req.use_web is False
        assert req.model == "qwen3.5:397b-cloud"
    
    def test_chat_request_full(self):
        """Test: Vollständige Request mit allen Optionen."""
        data = {
            "query": "Wie ist das Wetter heute?",
            "user_id": "user_123",
            "use_web": True,
            "model": "llama3.2:3b",
        }
        req = ChatRequest.from_json(data)
        
        assert req.query == "Wie ist das Wetter heute?"
        assert req.user_id == "user_123"
        assert req.use_web is True
        assert req.model == "llama3.2:3b"
    
    def test_chat_request_empty_query(self):
        """Test: Leere Query wird gehandhabt."""
        data = {
            "query": "",
            "user_id": "test_user",
        }
        req = ChatRequest.from_json(data)
        assert req.query == ""
    
    def test_chat_request_missing_user_id(self):
        """Test: Fehlende user_id bekommt Default."""
        data = {
            "query": "Testfrage",
        }
        req = ChatRequest.from_json(data)
        assert req.user_id == "anonymous"


# ══════════════════════════════════════════════════════════════════════════
# Test: ChatHandler Initialization
# ══════════════════════════════════════════════════════════════════════════

class TestChatHandlerInit:
    """Tests für ChatHandler Initialisierung."""
    
    def test_chat_handler_init_default(self):
        """Test: ChatHandler mit Standard-URLs."""
        handler = ChatHandler(
            rag_api_url="http://localhost:8765",
            ollama_url="http://localhost:11434",
        )
        
        assert handler.rag_api_url == "http://localhost:8765"
        assert handler.ollama_url == "http://localhost:11434"
    
    def test_chat_handler_init_trailing_slash(self):
        """Test: Trailing Slashes werden entfernt."""
        handler = ChatHandler(
            rag_api_url="http://localhost:8765/",
            ollama_url="http://localhost:11434/",
        )
        
        assert handler.rag_api_url == "http://localhost:8765"
        assert handler.ollama_url == "http://localhost:11434"


# ══════════════════════════════════════════════════════════════════════════
# Test: ChatHandler._search_rag
# ══════════════════════════════════════════════════════════════════════════

class TestSearchRag:
    """Tests für RAG-Suche."""
    
    def test_search_rag_local(self, chat_handler, mock_rag_response):
        """Test: Lokale Query (kein Web)."""
        with patch("copilot_core.styx.chat_handler.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_rag_response
            mock_requests.post.return_value = mock_resp
            
            result = chat_handler._search_rag(
                query="Wie war der Energieverbrauch?",
                use_web=False,
            )
            
            assert result["query_type"] == "local"
            assert len(result["results"]) == 2
            assert len(result["sources"]) == 2
    
    def test_search_rag_web(self, chat_handler):
        """Test: Web-Query (mit SearXNG)."""
        mock_response = {
            "results": [
                {
                    "id": "web_123",
                    "content": "Aktuelles Wetter: 20°C, sonnig",
                    "source": "searxng",
                    "score": 0.92,
                },
            ],
            "sources": [
                {"id": "web_123", "score": 0.92, "source": "searxng"},
            ],
            "query_type": "web",
        }
        
        with patch("copilot_core.styx.chat_handler.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_requests.post.return_value = mock_resp
            
            result = chat_handler._search_rag(
                query="Wie ist das Wetter heute?",
                use_web=True,
            )
            
            assert result["query_type"] == "web"
            assert len(result["results"]) == 1
            assert result["results"][0]["source"] == "searxng"
    
    def test_search_rag_error(self, chat_handler):
        """Test: RAG-API Fehler wird gehandhabt."""
        with patch("copilot_core.styx.chat_handler.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_requests.post.return_value = mock_resp
            
            result = chat_handler._search_rag(
                query="Testfrage",
                use_web=False,
            )
            
            assert result["results"] == []
            assert result["sources"] == []
            assert "error" in result
    
    def test_search_rag_timeout(self, chat_handler):
        """Test: Timeout wird gehandhabt."""
        from requests import Timeout
        with patch("copilot_core.styx.chat_handler.requests") as mock_requests:
            mock_requests.post.side_effect = Timeout("Timeout")
            
            result = chat_handler._search_rag(
                query="Testfrage",
                use_web=False,
            )
            
            assert result["results"] == []
            assert "error" in result


# ══════════════════════════════════════════════════════════════════════════
# Test: ChatHandler._build_prompt
# ══════════════════════════════════════════════════════════════════════════

class TestBuildPrompt:
    """Tests für Prompt-Building."""
    
    def test_build_prompt_with_context(self, chat_handler, mock_rag_response):
        """Test: Prompt mit RAG-Kontext."""
        prompt = chat_handler._build_prompt(
            query="Wie war der Energieverbrauch?",
            rag_results=mock_rag_response,
        )
        
        assert "Basierend auf dem folgenden Kontext:" in prompt
        assert "Energieverbrauch gestern: 12.5 kWh" in prompt
        assert "Wie war der Energieverbrauch?" in prompt
        assert "[Quelle 1]" in prompt
        assert "[Quelle 2]" in prompt
    
    def test_build_prompt_no_context(self, chat_handler):
        """Test: Prompt ohne Kontext (fallback)."""
        rag_results = {
            "results": [],
            "sources": [],
            "query_type": "local",
        }
        
        prompt = chat_handler._build_prompt(
            query="Testfrage ohne Kontext",
            rag_results=rag_results,
        )
        
        assert "Beantworte die folgende Frage" in prompt
        assert "Testfrage ohne Kontext" in prompt
        assert "Basierend auf dem folgenden Kontext:" not in prompt
    
    def test_build_prompt_query_type_included(self, chat_handler, mock_rag_response):
        """Test: Query-Type wird im Prompt berücksichtigt."""
        mock_rag_response["query_type"] = "web"
        
        prompt = chat_handler._build_prompt(
            query="Wie ist das Wetter?",
            rag_results=mock_rag_response,
        )
        
        assert "Quelle" in prompt


# ══════════════════════════════════════════════════════════════════════════
# Test: ChatHandler._call_ollama
# ══════════════════════════════════════════════════════════════════════════

class TestCallOllama:
    """Tests für Ollama-Inferenz."""
    
    def test_call_ollama_success(self, chat_handler, mock_ollama_response):
        """Test: Ollama-Aufruf erfolgreich."""
        with patch("copilot_core.styx.chat_handler.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_ollama_response
            mock_requests.post.return_value = mock_resp
            
            response = chat_handler._call_ollama(
                prompt="Testprompt",
                model="qwen3.5:397b-cloud",
            )
            
            assert response == "Der Energieverbrauch gestern betrug 12.5 kWh."
    
    def test_call_ollama_error(self, chat_handler):
        """Test: Ollama-Fehler wird gehandhabt."""
        with patch("copilot_core.styx.chat_handler.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_requests.post.return_value = mock_resp
            
            response = chat_handler._call_ollama(
                prompt="Testprompt",
                model="qwen3.5:397b-cloud",
            )
            
            assert "Entschuldigung" in response
            assert "500" in response
    
    def test_call_ollama_custom_model(self, chat_handler, mock_ollama_response):
        """Test: Custom Model wird verwendet."""
        with patch("copilot_core.styx.chat_handler.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_ollama_response
            mock_requests.post.return_value = mock_resp
            
            chat_handler._call_ollama(
                prompt="Testprompt",
                model="llama3.2:3b",
            )
            
            # Verify model was passed correctly
            call_args = mock_requests.post.call_args
            payload = call_args[1]["json"]
            assert payload["model"] == "llama3.2:3b"


# ══════════════════════════════════════════════════════════════════════════
# Test: ChatHandler.handle_query (Integration)
# ══════════════════════════════════════════════════════════════════════════

class TestHandleQuery:
    """Integration-Tests für handle_query."""
    
    def test_handle_query_local(self, chat_handler, mock_rag_response, mock_ollama_response):
        """Test: Lokale Query (kein Web)."""
        with patch.object(chat_handler, "_search_rag", return_value=mock_rag_response):
            with patch.object(chat_handler, "_call_ollama", return_value=mock_ollama_response["response"]):
                with patch.object(chat_handler, "_log_interaction"):
                    
                    result = chat_handler.handle_query(
                        query="Wie war der Energieverbrauch?",
                        user_id="test_user",
                        use_web=False,
                    )
                    
                    assert result["query_type"] == "local"
                    assert len(result["sources"]) == 2
                    assert result["response"] == "Der Energieverbrauch gestern betrug 12.5 kWh."
    
    def test_handle_query_web(self, chat_handler, mock_ollama_response):
        """Test: Web-Query (mit SearXNG)."""
        mock_web_response = {
            "results": [
                {
                    "id": "web_123",
                    "content": "Aktuelles Wetter: 20°C, sonnig",
                    "source": "searxng",
                    "score": 0.92,
                },
            ],
            "sources": [
                {"id": "web_123", "score": 0.92, "source": "searxng"},
            ],
            "query_type": "web",
        }
        
        with patch.object(chat_handler, "_search_rag", return_value=mock_web_response):
            with patch.object(chat_handler, "_call_ollama", return_value=mock_ollama_response["response"]):
                with patch.object(chat_handler, "_log_interaction"):
                    
                    result = chat_handler.handle_query(
                        query="Wie ist das Wetter heute?",
                        user_id="test_user",
                        use_web=True,
                    )
                    
                    assert result["query_type"] == "web"
                    assert len(result["sources"]) == 1
                    assert result["sources"][0]["source"] == "searxng"
    
    def test_handle_query_logs_interaction(self, chat_handler, mock_rag_response, mock_ollama_response):
        """Test: History wird geloggt."""
        with patch.object(chat_handler, "_search_rag", return_value=mock_rag_response):
            with patch.object(chat_handler, "_call_ollama", return_value=mock_ollama_response["response"]):
                mock_log = MagicMock()
                with patch.object(chat_handler, "_log_interaction", mock_log):
                    
                    chat_handler.handle_query(
                        query="Testfrage",
                        user_id="test_user_123",
                        use_web=False,
                    )
                    
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args
                    assert call_args[0][0] == "test_user_123"
                    assert call_args[0][1] == "Testfrage"


# ══════════════════════════════════════════════════════════════════════════
# Test: API Endpoint
# ══════════════════════════════════════════════════════════════════════════

class TestStyxChatEndpoint:
    """Tests für /api/styx/chat Endpoint."""
    
    def _create_test_client(self):
        """Erstelle Flask Test-Client für Styx Chat Blueprint."""
        from flask import Flask
        from copilot_core.api.v1.styx_chat import bp as styx_bp
        
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(styx_bp)
        return app.test_client()
    
    def test_styx_chat_missing_query(self):
        """Test: Fehlende Query wird abgelehnt."""
        client = self._create_test_client()
        response = client.post(
            "/api/styx/chat",
            json={"user_id": "test_user"},
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        assert "query is required" in data["error"]
    
    def test_styx_chat_missing_user_id(self):
        """Test: Fehlende user_id wird abgelehnt."""
        client = self._create_test_client()
        response = client.post(
            "/api/styx/chat",
            json={"query": "Testfrage"},
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        assert "user_id is required" in data["error"]
    
    def test_styx_chat_success(self, mock_rag_response, mock_ollama_response):
        """Test: Erfolgreicher Chat-Request."""
        client = self._create_test_client()
        
        with patch("copilot_core.api.v1.styx_chat._get_chat_handler") as mock_handler_getter:
            mock_handler = MagicMock()
            mock_handler.handle_query.return_value = {
                "response": mock_ollama_response["response"],
                "sources": mock_rag_response["sources"],
                "query_type": "local",
                "context_used": mock_rag_response["results"],
            }
            mock_handler_getter.return_value = mock_handler
            
            response = client.post(
                "/api/styx/chat",
                json={
                    "query": "Wie war der Energieverbrauch?",
                    "user_id": "test_user",
                    "use_web": False,
                },
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["ok"] is True
            assert data["response"] == mock_ollama_response["response"]
            assert len(data["sources"]) == 2
            assert data["query_type"] == "local"


# ══════════════════════════════════════════════════════════════════════════
# Test: Health Endpoint
# ══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    """Tests für /api/styx/health Endpoint."""
    
    def _create_test_client(self):
        """Erstelle Flask Test-Client für Styx Chat Blueprint."""
        from flask import Flask
        from copilot_core.api.v1.styx_chat import bp as styx_bp
        
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(styx_bp)
        return app.test_client()
    
    def test_styx_health(self):
        """Test: Health-Check Endpoint existiert."""
        client = self._create_test_client()
        response = client.get("/api/styx/health")
        
        # Endpoint sollte existieren (Status 200 oder 503 je nach Service-Status)
        assert response.status_code in [200, 503]
        data = response.get_json()
        assert "ok" in data
        assert "services" in data


# ══════════════════════════════════════════════════════════════════════════
# Test: Edge Cases
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Tests für Edge-Cases."""
    
    def test_empty_rag_results(self, chat_handler, mock_ollama_response):
        """Test: Leere RAG-Ergebnisse werden gehandhabt."""
        empty_response = {
            "results": [],
            "sources": [],
            "query_type": "local",
        }
        
        with patch.object(chat_handler, "_search_rag", return_value=empty_response):
            with patch.object(chat_handler, "_call_ollama", return_value=mock_ollama_response["response"]):
                
                result = chat_handler.handle_query(
                    query="Testfrage ohne Kontext",
                    user_id="test_user",
                    use_web=False,
                )
                
                assert result["query_type"] == "local"
                assert len(result["sources"]) == 0
    
    def test_very_long_query(self, chat_handler, mock_rag_response, mock_ollama_response):
        """Test: Sehr lange Query wird gehandhabt."""
        long_query = "Frage " * 1000  # 5000 Zeichen
        
        with patch.object(chat_handler, "_search_rag", return_value=mock_rag_response):
            with patch.object(chat_handler, "_call_ollama", return_value=mock_ollama_response["response"]):
                with patch.object(chat_handler, "_log_interaction"):
                    
                    result = chat_handler.handle_query(
                        query=long_query,
                        user_id="test_user",
                        use_web=False,
                    )
                    
                    assert result["response"] == mock_ollama_response["response"]
    
    def test_special_characters_in_query(self, chat_handler, mock_rag_response, mock_ollama_response):
        """Test: Special Characters in Query."""
        special_query = "Wie war der Verbrauch? <>&\"'äöü"
        
        with patch.object(chat_handler, "_search_rag", return_value=mock_rag_response):
            with patch.object(chat_handler, "_call_ollama", return_value=mock_ollama_response["response"]):
                with patch.object(chat_handler, "_log_interaction"):
                    
                    result = chat_handler.handle_query(
                        query=special_query,
                        user_id="test_user",
                        use_web=False,
                    )
                    
                    assert result["response"] == mock_ollama_response["response"]


# ══════════════════════════════════════════════════════════════════════════
# Test: Query Types
# ══════════════════════════════════════════════════════════════════════════

class TestQueryTypes:
    """Tests für verschiedene Query-Typen."""
    
    def test_local_query_type(self, chat_handler):
        """Test: Lokale Query (kein Web)."""
        mock_response = {
            "results": [{"id": "1", "content": "Lokal", "source": "ha_states", "score": 0.9}],
            "sources": [{"id": "1", "score": 0.9, "source": "ha_states"}],
            "query_type": "local",
        }
        
        with patch.object(chat_handler, "_search_rag", return_value=mock_response):
            with patch.object(chat_handler, "_call_ollama", return_value="Antwort"):
                with patch.object(chat_handler, "_log_interaction"):
                    
                    result = chat_handler.handle_query(
                        query="Wie war der Energieverbrauch?",
                        user_id="test_user",
                        use_web=False,
                    )
                    
                    assert result["query_type"] == "local"
    
    def test_web_query_type(self, chat_handler):
        """Test: Web-Query (mit SearXNG)."""
        mock_response = {
            "results": [{"id": "1", "content": "Web", "source": "searxng", "score": 0.9}],
            "sources": [{"id": "1", "score": 0.9, "source": "searxng"}],
            "query_type": "web",
        }
        
        with patch.object(chat_handler, "_search_rag", return_value=mock_response):
            with patch.object(chat_handler, "_call_ollama", return_value="Antwort"):
                with patch.object(chat_handler, "_log_interaction"):
                    
                    result = chat_handler.handle_query(
                        query="Wie ist das Wetter heute?",
                        user_id="test_user",
                        use_web=True,
                    )
                    
                    assert result["query_type"] == "web"


# ══════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════
# Test: Backend Services Health Check Endpoint
# ══════════════════════════════════════════════════════════════════════════

class TestStyxHealthBackend:
    """Tests für /api/styx/health/backend Endpoint."""
    
    @pytest.fixture
    def client(self):
        """Erstelle Test-Client mit styx_chat Blueprint."""
        from flask import Flask
        from copilot_core.api.v1.styx_chat import bp
        
        app = Flask(__name__)
        app.register_blueprint(bp)
        app.config["COPILOT_SERVICES"] = {}
        
        with app.test_client() as client:
            yield client
    
    def test_health_backend_empty_services(self, client):
        """Test: Health Check mit leeren Services."""
        response = client.get("/api/styx/health/backend")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["ok"] is True
        assert data["total_services"] == 0
        assert data["unhealthy_services"] == []
        assert "timestamp" in data
        assert "services" in data
    
    def test_health_backend_with_services(self, client):
        """Test: Health Check mit Services (ein fehlender -> 503)."""
        # Mock Services
        mock_brain_graph = MagicMock()
        mock_brain_graph.health_check = MagicMock(return_value={"status": "ok"})
        
        mock_conversation = MagicMock()
        mock_conversation.get_status = MagicMock(return_value={"status": "ok"})
        
        client.application.config["COPILOT_SERVICES"] = {
            "brain_graph_service": mock_brain_graph,
            "conversation_memory": mock_conversation,
            "habitus_service": None,  # Missing service
        }
        
        response = client.get("/api/styx/health/backend")
        
        # Should return 503 because habitus_service is missing
        assert response.status_code == 503
        data = response.get_json()
        
        assert data["ok"] is False  # Weil habitus_service missing
        assert data["total_services"] == 3
        assert "habitus_service" in data["unhealthy_services"]
        assert "brain_graph_service" not in data["unhealthy_services"]
        assert "conversation_memory" not in data["unhealthy_services"]
    
    def test_health_backend_all_healthy(self, client):
        """Test: Health Check mit allen healthy Services."""
        mock_service = MagicMock()
        mock_service.health_check = MagicMock(return_value={"status": "ok"})
        
        client.application.config["COPILOT_SERVICES"] = {
            "service_a": mock_service,
            "service_b": mock_service,
        }
        
        response = client.get("/api/styx/health/backend")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["ok"] is True
        assert data["total_services"] == 2
        assert data["unhealthy_services"] == []


# Run Tests
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
