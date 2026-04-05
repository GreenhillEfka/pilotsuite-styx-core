from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

core_app_root_str = str(CORE_APP_ROOT)
if core_app_root_str not in sys.path:
    sys.path.insert(0, core_app_root_str)

from copilot_core.api.v1 import rag as module  # noqa: E402


class FakeCache:
    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}
        self.invalidated_patterns: list[str] = []
        self.cleared_patterns: list[str] = []
        self.raise_on: str | None = None

    async def get(self, key: str):
        if self.raise_on == "get":
            raise RuntimeError("cache get exploded")
        return self.entries.get(key)

    async def set(self, key: str, value: dict):
        if self.raise_on == "set":
            raise RuntimeError("cache set exploded")
        self.entries[key] = value

    def invalidate_pattern(self, pattern: str) -> None:
        if self.raise_on == "invalidate":
            raise RuntimeError("cache invalidate exploded")
        self.invalidated_patterns.append(pattern)

    async def get_stats(self):
        if self.raise_on == "stats":
            raise RuntimeError("cache stats exploded")
        return {
            "hybrid": {"enabled": True, "metrics": {"hit_rate": 0.75}},
            "local": {"size": len(self.entries), "max_size": 1000},
            "redis": {"connected": False},
        }

    async def clear(self):
        if self.raise_on == "clear":
            raise RuntimeError("cache clear exploded")
        self.entries.clear()
        return 0

    async def clear_by_pattern(self, pattern: str):
        if self.raise_on == "clear":
            raise RuntimeError("cache clear exploded")
        self.cleared_patterns.append(pattern)
        return 3


class FakeBM25:
    def __init__(self) -> None:
        self.raise_on: str | None = None
        self.documents = {
            "doc-1": {"text": "Wohnzimmer Licht Status", "metadata": {"room": "living"}},
            "doc-2": {"text": "Kueche Licht Szene", "metadata": {"room": "kitchen"}},
            "doc-3": {"text": "Wetter Web Kontext", "metadata": {"room": "outside"}},
        }
        self.last_upsert_namespace: str | None = None
        self.last_upsert_ids: list[str] = []

    def search(self, namespace: str, query: str, top_k: int, include_text: bool, include_metadata: bool):
        if self.raise_on == "search":
            raise RuntimeError("bm25 exploded")
        hits = [
            module.BM25Hit(
                doc_id="doc-1",
                score=0.91,
                rank=1,
                text=self.documents["doc-1"]["text"] if include_text else None,
                metadata=self.documents["doc-1"]["metadata"] if include_metadata else None,
            ),
            module.BM25Hit(
                doc_id="doc-2",
                score=0.62,
                rank=2,
                text=self.documents["doc-2"]["text"] if include_text else None,
                metadata=self.documents["doc-2"]["metadata"] if include_metadata else None,
            ),
        ]
        return hits[:top_k]

    def get_documents(self, namespace: str, doc_ids: list[str]):
        if self.raise_on == "get_documents":
            raise RuntimeError("documents exploded")
        return {doc_id: self.documents.get(doc_id, {}) for doc_id in doc_ids}

    def stats(self, namespace: str):
        if self.raise_on == "stats":
            raise RuntimeError("stats exploded")
        return SimpleNamespace(
            namespace=namespace,
            doc_count=3,
            term_count=9,
            posting_count=12,
            avg_doc_len=3.0,
            total_doc_len=9,
            updated_at="2026-04-05T01:12:00Z",
            db_path="/tmp/rag.sqlite3",
            db_size_bytes=2048,
            schema_version=1,
        )

    def upsert_documents(self, namespace: str, documents: list):
        if self.raise_on == "upsert":
            raise RuntimeError("index exploded")
        self.last_upsert_namespace = namespace
        self.last_upsert_ids = [document.doc_id for document in documents]
        for document in documents:
            self.documents[document.doc_id] = {
                "text": document.text,
                "metadata": document.metadata,
            }
        return len(documents), []


def _classification_for(query: str):
    if "weather" in query.lower():
        return SimpleNamespace(
            query_type=module.QueryType.WEB,
            confidence=0.93,
            web_keywords_found=["weather"],
            local_keywords_found=[],
            reasoning="weather intent detected",
            use_web_search=True,
        )
    return SimpleNamespace(
        query_type=module.QueryType.LOCAL,
        confidence=0.88,
        web_keywords_found=[],
        local_keywords_found=["licht"],
        reasoning="local entity lookup",
        use_web_search=False,
    )


def _build_client(monkeypatch, *, authorized: bool = True, bm25: FakeBM25 | None = None, cache: FakeCache | None = None):
    module.init_rag_api()
    bm25 = bm25 or FakeBM25()
    cache = cache or FakeCache()
    runtime_globals = module.rag_search.__globals__

    monkeypatch.setitem(runtime_globals, "validate_token", lambda _request: authorized)
    monkeypatch.setitem(runtime_globals, "_rate_limit_rag", lambda: None)
    monkeypatch.setitem(runtime_globals, "_get_bm25", lambda: bm25)
    monkeypatch.setitem(
        runtime_globals,
        "_semantic_search",
        lambda **kwargs: [
            module.RankedHit(doc_id="doc-2", score=0.81, rank=1),
            module.RankedHit(doc_id="doc-1", score=0.55, rank=2),
        ][: kwargs.get("top_k", 10)],
    )
    monkeypatch.setitem(runtime_globals, "_semantic_index", lambda **kwargs: len(kwargs["documents"]))
    monkeypatch.setitem(runtime_globals, "_get_rag_cache", lambda: cache)
    monkeypatch.setitem(runtime_globals, "classify_query", _classification_for)
    monkeypatch.setitem(
        runtime_globals,
        "_searxng_search_sync",
        lambda query, categories=None, top_k=10, warnings=None: [
            SimpleNamespace(
                url="https://example.com/weather",
                title="Weather Result",
                content="Wetterlage fuer heute",
                score=0.77,
                category=(categories or ["general"])[0],
                engine="duckduckgo",
            ),
            SimpleNamespace(
                url="https://example.com/forecast",
                title="Forecast Result",
                content="Vorhersage fuer morgen",
                score=0.66,
                category=(categories or ["general"])[0],
                engine="wikipedia",
            ),
        ][:top_k],
    )

    app = Flask(__name__)
    app.register_blueprint(module.bp)
    return app.test_client(), bm25, cache


def test_rag_contract_covers_all_routes(monkeypatch) -> None:
    client, bm25, cache = _build_client(monkeypatch)

    response = client.post("/api/v1/rag/search", json={"namespace": "home", "query": "licht", "top_k": 2})
    assert response.status_code == 200
    search = response.get_json()
    assert search["mode"] == "hybrid_rrf"
    assert search["result_count"] == 2
    assert search["results"][0]["id"] == "doc-1"
    assert search["cache_hit"] is False

    response = client.post("/api/v1/rag/search", json={"namespace": "home", "query": "licht", "top_k": 2})
    assert response.status_code == 200
    cached = response.get_json()
    assert cached["cache_hit"] is True
    assert cached["result_count"] == 2

    response = client.post("/api/v1/rag/search/bm25", json={"namespace": "home", "query": "licht", "top_k": 1})
    assert response.status_code == 200
    bm25_search = response.get_json()
    assert bm25_search["mode"] == "bm25"
    assert bm25_search["results"][0]["text"] == "Wohnzimmer Licht Status"

    response = client.post("/api/v1/rag/search/semantic", json={"namespace": "home", "query": "licht", "top_k": 1})
    assert response.status_code == 200
    semantic = response.get_json()
    assert semantic["mode"] == "semantic"
    assert semantic["results"][0]["id"] == "doc-2"

    response = client.post(
        "/api/v1/rag/rerank",
        json={
            "lexical_hits": [{"id": "doc-1", "score": 0.9, "rank": 1}],
            "semantic_hits": [{"id": "doc-2", "score": 0.8, "rank": 1}],
            "top_k": 2,
        },
    )
    assert response.status_code == 200
    rerank = response.get_json()
    assert rerank["result_count"] == 2

    response = client.get("/api/v1/rag/stats?namespace=home")
    assert response.status_code == 200
    stats = response.get_json()
    assert stats["doc_count"] == 3
    assert stats["metrics"]["cache"] == {
        "enabled": True,
        "hit_rate": 0.75,
        "local_size": 1,
        "local_max_size": 1000,
        "redis_connected": False,
    }

    response = client.post(
        "/api/v1/rag/index",
        json={
            "namespace": "home",
            "documents": [{"id": "doc-9", "text": "Neue Szene", "metadata": {"source": "test"}}],
            "index_semantic": True,
        },
    )
    assert response.status_code == 200
    indexed = response.get_json()
    assert indexed["bm25_indexed"] == 1
    assert indexed["semantic_indexed"] == 1
    assert indexed["cache_invalidated"] is True
    assert bm25.last_upsert_namespace == "home"
    assert bm25.last_upsert_ids == ["doc-9"]
    assert cache.invalidated_patterns == ["rag:*:home:*"]

    response = client.post("/api/v1/rag/cache/clear", json={"namespace": "home"})
    assert response.status_code == 200
    cleared = response.get_json()
    assert cleared["status"] == "ok"
    assert "namespace 'home'" in cleared["cleared"]
    assert cache.cleared_patterns == ["rag:*:home:*"]

    response = client.post(
        "/api/v1/rag/search/enhanced",
        json={"namespace": "home", "query": "weather now", "use_web": True, "top_k": 2},
    )
    assert response.status_code == 200
    enhanced = response.get_json()
    assert enhanced["mode"] == "web"
    assert enhanced["query_classification"]["type"] == module.QueryType.WEB.value
    assert enhanced["sources_used"] == {
        "local_bm25": True,
        "semantic": True,
        "web_searxng": True,
    }
    assert enhanced["results"][0]["source"] == "searxng"


def test_rag_contract_hardens_validation_and_runtime_errors(monkeypatch) -> None:
    bm25 = FakeBM25()
    cache = FakeCache()
    client, _, _ = _build_client(monkeypatch, bm25=bm25, cache=cache)

    response = client.post("/api/v1/rag/search")
    assert response.status_code == 400
    assert response.get_json() == {"error": "No JSON body provided"}

    response = client.post("/api/v1/rag/search", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/rag/search", json={"query": 7})
    assert response.status_code == 400
    assert response.get_json() == {"error": "query must be a string"}

    response = client.post("/api/v1/rag/search", json={"namespace": "../bad", "query": "licht"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid namespace format"}

    response = client.post("/api/v1/rag/search/bm25", json={"query": 7})
    assert response.status_code == 400
    assert response.get_json() == {"error": "query must be a string"}

    response = client.post("/api/v1/rag/search/semantic", json=[])
    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON body must be an object"}

    response = client.post("/api/v1/rag/rerank", json={"lexical_hits": "broken"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "lexical_hits must be a list"}

    response = client.post("/api/v1/rag/rerank", json={"lexical_hits": [7]})
    assert response.status_code == 400
    assert response.get_json() == {"error": "lexical_hits entries must be objects"}

    response = client.post("/api/v1/rag/index", json={"documents": "broken"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "documents must be a list"}

    response = client.post("/api/v1/rag/index", json={"documents": [{"id": 7, "text": "ok"}]})
    assert response.status_code == 400
    assert response.get_json() == {"error": "document id must be a string"}

    response = client.post("/api/v1/rag/cache/clear", json={"namespace": 7})
    assert response.status_code == 400
    assert response.get_json() == {"error": "namespace must be a string"}

    response = client.post("/api/v1/rag/search/enhanced", json={"query": "weather", "use_web": "yes"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "use_web must be a boolean"}

    response = client.post("/api/v1/rag/search/enhanced", json={"query": "weather", "searxng_categories": "news"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "searxng_categories must be a list of strings"}

    bm25.raise_on = "search"
    response = client.post("/api/v1/rag/search/bm25", json={"query": "licht"})
    assert response.status_code == 500
    assert response.get_json() == {"error": "bm25 exploded"}

    bm25.raise_on = "stats"
    response = client.get("/api/v1/rag/stats")
    assert response.status_code == 500
    assert response.get_json() == {"error": "stats exploded"}

    bm25.raise_on = "upsert"
    response = client.post("/api/v1/rag/index", json={"documents": [{"id": "doc-1", "text": "Hallo"}]})
    assert response.status_code == 500
    assert response.get_json() == {"error": "index exploded"}

    bm25.raise_on = None
    cache.raise_on = "clear"
    response = client.post("/api/v1/rag/cache/clear", json={"pattern": "home"})
    assert response.status_code == 500
    assert response.get_json() == {"error": "cache clear exploded"}


def test_rag_contract_requires_authentication(monkeypatch) -> None:
    client, _, _ = _build_client(monkeypatch, authorized=False)

    response = client.post("/api/v1/rag/search", json={"query": "licht"})
    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "error": "unauthorized"}
