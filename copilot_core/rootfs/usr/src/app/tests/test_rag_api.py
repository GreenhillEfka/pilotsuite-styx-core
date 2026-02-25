"""Tests for /api/v1/rag/* endpoints."""

from __future__ import annotations

import tempfile

from flask import Flask

from copilot_core.api.v1.rag import rag_bp, init_rag_api
from copilot_core.rag.service import RagService
from copilot_core.vector_store.embeddings import EmbeddingEngine, EmbeddingConfig
from copilot_core.vector_store.store import VectorStore, VectorStoreConfig


def _create_rag_app(tmpdir: str) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True

    store = VectorStore(VectorStoreConfig(db_path=f"{tmpdir}/rag_vectors.db", persist=True))
    engine = EmbeddingEngine(EmbeddingConfig(use_ollama=False))
    store.set_embedding_engine(engine)
    init_rag_api(RagService(store, engine))
    app.register_blueprint(rag_bp)
    return app


def test_rag_ingest_query_and_delete(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")

    with tempfile.TemporaryDirectory() as tmpdir:
        app = _create_rag_app(tmpdir)
        client = app.test_client()

        ingest = client.post(
            "/api/v1/rag/documents",
            json={
                "doc_id": "lights_manual",
                "source": "manual_lights.md",
                "text": "Wenn Bewegung im Wohnbereich erkannt wird und es dunkel ist, "
                "soll das Licht im Wohnbereich auf warmes weiss eingeschaltet werden.",
                "tags": ["licht", "wohnbereich"],
            },
        )
        assert ingest.status_code == 201
        ingest_payload = ingest.get_json()
        assert ingest_payload["ok"] is True
        assert ingest_payload["result"]["chunks_indexed"] >= 1

        status = client.get("/api/v1/rag/status")
        assert status.status_code == 200
        status_payload = status.get_json()
        assert status_payload["ok"] is True
        assert status_payload["rag"]["document_count"] >= 1

        query = client.post(
            "/api/v1/rag/query",
            json={"query": "Wie steuere ich Licht bei Bewegung?", "limit": 3},
        )
        assert query.status_code == 200
        query_payload = query.get_json()
        assert query_payload["ok"] is True
        assert query_payload["count"] >= 1
        assert query_payload["results"][0]["doc_id"] == "lights_manual"

        documents = client.get("/api/v1/rag/documents")
        assert documents.status_code == 200
        docs_payload = documents.get_json()
        assert docs_payload["ok"] is True
        assert any(d["doc_id"] == "lights_manual" for d in docs_payload["documents"])

        deleted = client.delete("/api/v1/rag/documents/lights_manual")
        assert deleted.status_code == 200
        deleted_payload = deleted.get_json()
        assert deleted_payload["ok"] is True
        assert deleted_payload["deleted_chunks"] >= 1
