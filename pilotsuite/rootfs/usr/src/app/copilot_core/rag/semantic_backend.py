"""Default Semantic Backend for RAG Pipeline.

Uses the existing VectorStore + EmbeddingEngine from core_setup services
to provide semantic search alongside BM25 lexical search.

This module is auto-discovered by the RAG API when no external
COPILOT_CORE_RAG_SEMANTIC_BACKEND env var is set.

API Contract (matches _SemanticBackend in rag.py):
  - rag_semantic_index(namespace, documents) -> int
  - rag_semantic_search(namespace, query, top_k) -> list[dict]
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Sequence

logger = logging.getLogger(__name__)


def _get_engines():
    """Get VectorStore + EmbeddingEngine from Flask app services."""
    try:
        from flask import current_app
        services = current_app.config.get("COPILOT_SERVICES", {})
        vs = services.get("vector_store")
        ee = services.get("embedding_engine")
        return vs, ee
    except RuntimeError:
        return None, None


def rag_semantic_index(
    *,
    namespace: str,
    documents: Sequence[Dict[str, Any]],
) -> int:
    """Index documents into VectorStore for semantic search.

    Args:
        namespace: Document namespace (e.g., "ha_docs", "user_notes")
        documents: List of {id, text, metadata} dicts

    Returns:
        Number of successfully indexed documents.
    """
    vs, ee = _get_engines()
    if not vs or not ee:
        logger.debug("VectorStore/EmbeddingEngine not available for semantic indexing")
        return 0

    indexed = 0
    for doc in documents:
        doc_id = doc.get("id") or doc.get("doc_id", "")
        text = doc.get("text", "")
        metadata = doc.get("metadata", {})

        if not doc_id or not text:
            continue

        try:
            embedding = ee.embed(text)
            if embedding is None:
                continue

            vs.upsert(
                entry_id=f"rag:{namespace}:{doc_id}",
                vector=embedding,
                entry_type="rag_document",
                metadata={
                    "namespace": namespace,
                    "doc_id": doc_id,
                    "snippet": text[:300],
                    "timestamp": time.time(),
                    **metadata,
                },
            )
            indexed += 1
        except Exception as exc:
            logger.debug("Semantic index failed for %s: %s", doc_id, exc)

    if indexed > 0:
        logger.info("Semantic: indexed %d/%d docs (namespace=%s)", indexed, len(documents), namespace)
    return indexed


def rag_semantic_search(
    *,
    namespace: str,
    query: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Search VectorStore semantically.

    Args:
        namespace: Document namespace to search in
        query: Search query text
        top_k: Max results

    Returns:
        List of {id, score, text, metadata} dicts.
    """
    vs, ee = _get_engines()
    if not vs or not ee:
        return []

    try:
        query_embedding = ee.embed(query)
        if query_embedding is None:
            return []

        hits = vs.search(query_embedding, top_k=top_k * 2)  # Over-fetch for namespace filter

        results = []
        for hit in hits:
            meta = hit.get("metadata", {})
            # Filter by namespace
            if meta.get("namespace") != namespace:
                continue

            results.append({
                "id": meta.get("doc_id", hit.get("id", "")),
                "score": hit.get("score", 0.0),
                "text": meta.get("snippet", ""),
                "metadata": meta,
            })

            if len(results) >= top_k:
                break

        return results

    except Exception as exc:
        logger.warning("Semantic search failed: %s", exc)
        return []
# Backwards compatibility alias
SemanticBackend = object  # Placeholder — _SemanticBackend lives in rag.py
