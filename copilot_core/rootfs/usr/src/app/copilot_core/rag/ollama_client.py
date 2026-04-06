"""Ollama RAG Client — Semantic Search via Ollama Embeddings.

Provides semantic search using Ollama's embedding models (nomic-embed-text, etc.)
with hybrid search support (RRF fusion with BM25).

Usage:
    client = OllamaRAGClient()
    results = client.search("Heizung einschalten", top_k=5, rerank=True)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

import requests

from .bm25 import BM25Config, BM25Document, BM25SqliteIndex
from .hybrid_search import FusedHit, RankedHit, reciprocal_rank_fusion

_LOGGER = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────


@dataclass
class OllamaRAGConfig:
    """Configuration for Ollama RAG client."""

    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    chat_model: str = "qwen3:4b"
    embedding_dim: int = 768
    timeout: float = 30.0
    cache_embeddings: bool = True


# ─── Embedding Client ────────────────────────────────────────────────────────


class OllamaEmbeddingClient:
    """Ollama embedding generation client."""

    def __init__(self, config: Optional[OllamaRAGConfig] = None) -> None:
        self._config = config or OllamaRAGConfig()
        self._session = requests.Session()
        self._cache: dict[str, List[float]] = {}

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.

        Uses Ollama /api/embeddings endpoint.
        Falls back to hash-based pseudo-embeddings if Ollama unavailable.
        """
        # Check cache
        cached = []
        uncached_idx = []
        uncached_texts = []

        for i, text in enumerate(texts):
            if self._config.cache_embeddings and text in self._cache:
                cached.append(self._cache[text])
            else:
                cached.append(None)
                uncached_idx.append(i)
                uncached_texts.append(text)

        # Fetch all uncached embeddings
        if uncached_texts:
            try:
                embeddings = self._fetch_embeddings(uncached_texts)
                for idx, emb in zip(uncached_idx, embeddings):
                    if self._config.cache_embeddings:
                        self._cache[uncached_texts[uncached_idx.index(idx)]] = emb
                    cached[idx] = emb
            except Exception as exc:
                _LOGGER.warning("Ollama embedding failed, using fallback: %s", exc)
                # Fallback: deterministic hash embeddings
                for idx in uncached_idx:
                    cached[idx] = self._hash_embedding(uncached_texts[uncached_idx.index(idx)])

        return cached  # type: ignore[return-value]

    def _fetch_embeddings(self, texts: Sequence[str]) -> List[List[float]]:
        """Call Ollama /api/embeddings."""
        embeddings: List[List[float]] = []
        for text in texts:
            resp = self._session.post(
                f"{self._config.ollama_url}/api/embeddings",
                json={"model": self._config.embedding_model, "prompt": text},
                timeout=self._config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if not embedding:
                embedding = self._hash_embedding(text)
            embeddings.append(embedding)
        return embeddings

    def _hash_embedding(self, text: str) -> List[float]:
        """Fallback deterministic embedding when Ollama unavailable."""
        import hashlib
        import math
        dim = self._config.embedding_dim
        vec = []
        for i in range(dim):
            h = hashlib.md5(f"{text}:{i}".encode()).hexdigest()
            val = int(h[:8], 16) / (16**8) * 2 - 1
            vec.append(val)
        # Normalize
        mag = math.sqrt(sum(x * x for x in vec))
        return [x / mag for x in vec] if mag > 0 else vec


# ─── Ollama RAG Client ───────────────────────────────────────────────────────


class OllamaRAGClient:
    """Hybrid RAG client: BM25 + Semantic (Ollama embeddings) + RRF reranking.

    Usage:
        client = OllamaRAGClient()
        results = client.search("query", top_k=5, rerank=True)
    """

    def __init__(self, config: Optional[OllamaRAGConfig] = None) -> None:
        self._config = config or OllamaRAGConfig()
        self._embed = OllamaEmbeddingClient(self._config)
        self._bm25_index: Optional[BM25SqliteIndex] = None

    def index_documents(self, documents: Sequence[dict[str, Any]]) -> int:
        """Index documents into BM25 + in-memory vector store.

        Each document: {id, text, metadata}
        """
        # BM25 indexing
        if not self._bm25_index:
            self._bm25_index = BM25SqliteIndex(":memory:")
            self._bm25_config = BM25Config()

        docs = [
            BM25Document(doc_id=d["id"], text=d["text"], metadata=d.get("metadata", {}))
            for d in documents
        ]
        self._bm25_index.add_documents(docs, config=self._bm25_config)

        # Store for semantic retrieval
        if not hasattr(self, "_semantic_docs"):
            self._semantic_docs: dict[str, dict] = {}
        for d in documents:
            self._semantic_docs[d["id"]] = d

        return len(documents)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        rerank: bool = True,
        namespace: str = "default",
    ) -> List[dict[str, Any]]:
        """Hybrid search: BM25 + semantic + RRF reranking.

        Args:
            query: Search query text
            top_k: Number of results to return
            rerank: Whether to apply RRF reranking (default True)
            namespace: Document namespace (reserved for future multi-namespace)

        Returns:
            List of search results with doc_id, text, metadata, score, rank
        """
        if not self._bm25_index:
            _LOGGER.debug("No documents indexed yet")
            return []

        # BM25 search
        bm25_hits = self._bm25_index.search(query, top_k=top_k * 2)
        lexical_hits = [
            RankedHit(doc_id=h.doc_id, score=h.score, rank=i + 1)
            for i, h in enumerate(bm25_hits)
        ]

        # Semantic search
        try:
            query_emb = self._embed.embed([query])[0]
        except Exception as exc:
            _LOGGER.warning("Semantic search failed: %s", exc)
            query_emb = None

        semantic_hits: List[RankedHit] = []
        if query_emb and hasattr(self, "_semantic_docs") and self._semantic_docs:
            doc_ids = list(self._semantic_docs.keys())
            doc_texts = [self._semantic_docs[did]["text"] for did in doc_ids]
            doc_embs = self._embed.embed(doc_texts)

            # Cosine similarity
            similarities = []
            for did, demb in zip(doc_ids, doc_embs):
                sim = self._cosine(query_emb, demb)
                similarities.append((did, sim))
            similarities.sort(key=lambda x: x[1], reverse=True)

            for rank, (did, sim) in enumerate(similarities[: top_k * 2], 1):
                semantic_hits.append(RankedHit(doc_id=did, score=sim, rank=rank))

        # RRF fusion
        if rerank and semantic_hits:
            fused = reciprocal_rank_fusion(
                lexical_hits=lexical_hits,
                semantic_hits=semantic_hits,
                top_k=top_k,
                k=60,
                lexical_weight=1.0,
                semantic_weight=1.0,
            )
        else:
            # BM25 only
            fused = [
                FusedHit(doc_id=h.doc_id, fused_score=h.score,
                         lexical_rank=h.rank, lexical_score=h.score)
                for h in lexical_hits[:top_k]
            ]

        # Build results
        results = []
        for fhit in fused:
            doc = (getattr(self, "_semantic_docs", {}) or {}).get(fhit.doc_id, {})
            results.append({
                "doc_id": fhit.doc_id,
                "text": doc.get("text", ""),
                "metadata": doc.get("metadata", {}),
                "score": round(fhit.fused_score, 4),
                "lexical_rank": fhit.lexical_rank,
                "semantic_rank": fhit.semantic_rank,
            })

        return results

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        return dot / (mag_a * mag_b + 1e-8)

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        return OllamaRAGClient._cosine(a, b)
