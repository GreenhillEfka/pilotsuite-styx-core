from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import rag_ui as module  # noqa: E402


def _build_client():
    app = Flask(__name__)
    app.register_blueprint(module.rag_ui_bp)
    return app.test_client()


def test_rag_ui_static_surfaces_and_success_paths() -> None:
    client = _build_client()

    response = client.get("/api/v1/rag")
    assert response.status_code == 200
    overview = response.get_json()
    assert overview["vectors"]["count"] == 1500
    assert overview["searxng"]["status"] == "healthy"
    assert overview["voice"]["model"] == "whisper"

    response = client.get("/api/v1/rag/vectors?limit=2&offset=1&query=wohnzimmer")
    assert response.status_code == 200
    vectors = response.get_json()
    assert vectors["limit"] == 2
    assert vectors["offset"] == 1
    assert vectors["query"] == "wohnzimmer"
    assert [entry["id"] for entry in vectors["vectors"]] == ["vec_0001", "vec_0002"]

    response = client.get("/api/v1/rag/embeddings?limit=3")
    assert response.status_code == 200
    embeddings = response.get_json()
    assert embeddings["limit"] == 3
    assert len(embeddings["embeddings"]) == 3

    response = client.get("/api/v1/rag/search?limit=2")
    assert response.status_code == 200
    search_log = response.get_json()
    assert search_log["limit"] == 2
    assert len(search_log["searches"]) == 2

    response = client.post("/api/v1/rag/search", json={"query": "licht"})
    assert response.status_code == 200
    search_result = response.get_json()
    assert search_result["query"] == "licht"
    assert len(search_result["results"]) == 5
    assert search_result["results"][0]["text"] == "Ergebnis 0 für 'licht'"

    response = client.get("/api/v1/rag/searxng")
    assert response.status_code == 200
    searxng = response.get_json()
    assert searxng["engines"] == ["google", "bing", "duckduckgo", "wikipedia"]

    response = client.post(
        "/api/v1/rag/searxng/search",
        json={"query": "news", "categories": ["news", "science"]},
    )
    assert response.status_code == 200
    searxng_search = response.get_json()
    assert searxng_search["categories"] == ["news", "science"]
    assert searxng_search["results"][0]["category"] == "news"

    response = client.get("/api/v1/rag/voice")
    assert response.status_code == 200
    voice = response.get_json()
    assert voice["status"] == "ready"
    assert voice["queries_today"] == 12

    response = client.post("/api/v1/rag/voice/query", json={"text": "Wie ist das Wetter?"})
    assert response.status_code == 200
    voice_query = response.get_json()
    assert voice_query == {
        "transcription": "Wie ist das Wetter?",
        "answer": "Antwort auf die Voice-Anfrage",
        "confidence": 0.95,
        "input_mode": "text",
    }


def test_rag_ui_query_and_payload_validation() -> None:
    client = _build_client()

    response = client.get("/api/v1/rag/vectors?limit=laut")
    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be an integer"}

    response = client.get("/api/v1/rag/vectors?offset=-1")
    assert response.status_code == 400
    assert response.get_json() == {"error": "offset must be >= 0"}

    response = client.get("/api/v1/rag/embeddings?limit=201")
    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be <= 200"}

    response = client.get("/api/v1/rag/search?limit=-5")
    assert response.status_code == 400
    assert response.get_json() == {"error": "limit must be >= 0"}

    response = client.post("/api/v1/rag/search")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body required"}

    response = client.post("/api/v1/rag/search", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/rag/search", json={"query": "   "})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Query required"}

    response = client.post("/api/v1/rag/searxng/search", json={"query": "haus", "categories": "general"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "categories must be a list of strings"}

    response = client.post("/api/v1/rag/voice/query", json={"text": 123})
    assert response.status_code == 400
    assert response.get_json() == {"error": "text must be a string"}

    response = client.post("/api/v1/rag/voice/query", json={"audio": 123})
    assert response.status_code == 400
    assert response.get_json() == {"error": "audio must be a string"}

    response = client.post("/api/v1/rag/voice/query", json={})
    assert response.status_code == 400
    assert response.get_json() == {"error": "Audio or text required"}


def test_rag_ui_runtime_errors_return_consistent_json(monkeypatch) -> None:
    client = _build_client()

    monkeypatch.setattr(module, "_build_rag_overview_payload", lambda: (_ for _ in ()).throw(RuntimeError("overview failed")))
    response = client.get("/api/v1/rag")
    assert response.status_code == 500
    assert response.get_json() == {"error": "overview failed"}

    monkeypatch.setattr(module, "_run_rag_search_payload", lambda query: (_ for _ in ()).throw(RuntimeError("search failed")))
    response = client.post("/api/v1/rag/search", json={"query": "licht"})
    assert response.status_code == 500
    assert response.get_json() == {"error": "search failed"}

    monkeypatch.setattr(module, "_build_searxng_status_payload", lambda: (_ for _ in ()).throw(RuntimeError("searxng status failed")))
    response = client.get("/api/v1/rag/searxng")
    assert response.status_code == 500
    assert response.get_json() == {"error": "searxng status failed"}

    monkeypatch.setattr(module, "_run_searxng_search_payload", lambda query, categories: (_ for _ in ()).throw(RuntimeError("searxng search failed")))
    response = client.post("/api/v1/rag/searxng/search", json={"query": "news", "categories": ["news"]})
    assert response.status_code == 500
    assert response.get_json() == {"error": "searxng search failed"}

    monkeypatch.setattr(module, "_run_voice_query_payload", lambda audio, text: (_ for _ in ()).throw(RuntimeError("voice failed")))
    response = client.post("/api/v1/rag/voice/query", json={"text": "Hallo"})
    assert response.status_code == 500
    assert response.get_json() == {"error": "voice failed"}
