"""RAG document service based on the existing vector store.

This service provides:
- document ingest with chunking
- semantic retrieval for prompt augmentation
- document listing and deletion
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from copilot_core.vector_store.store import VectorStore
from copilot_core.vector_store.embeddings import EmbeddingEngine

_LOGGER = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RagService:
    """RAG document ingestion and retrieval over VectorStore."""

    ENTRY_TYPE = "rag_document"
    ENTRY_PREFIX = "rag"

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_engine: EmbeddingEngine,
        *,
        default_chunk_size: int = 800,
        default_chunk_overlap: int = 120,
        default_threshold: float = 0.35,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_engine = embedding_engine
        self._default_chunk_size = max(120, int(default_chunk_size))
        self._default_chunk_overlap = max(0, int(default_chunk_overlap))
        self._default_threshold = max(0.0, min(1.0, float(default_threshold)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @staticmethod
    def _normalize_doc_id(doc_id: str) -> str:
        raw = str(doc_id or "").strip()
        safe = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", raw)
        return safe.strip("_") or "document"

    @staticmethod
    def _run_async(coro):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _split_chunks(
        self,
        text: str,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[str]:
        size = max(120, int(chunk_size or self._default_chunk_size))
        overlap = max(0, int(chunk_overlap if chunk_overlap is not None else self._default_chunk_overlap))
        overlap = min(overlap, size - 1)

        normalized = self._normalize_text(text)
        if not normalized:
            return []
        if len(normalized) <= size:
            return [normalized]

        chunks: list[str] = []
        start = 0
        n = len(normalized)
        while start < n:
            end = min(n, start + size)
            if end < n:
                split = normalized.rfind(" ", start, end)
                if split > start + int(size * 0.6):
                    end = split
            piece = normalized[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= n:
                break
            next_start = max(0, end - overlap)
            if next_start <= start:
                next_start = end
            start = next_start
        return chunks

    def _entry_id(self, doc_id: str, chunk_index: int) -> str:
        return f"{self.ENTRY_PREFIX}:{doc_id}:{chunk_index:05d}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_document(
        self,
        *,
        doc_id: str,
        text: str,
        source: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> dict[str, Any]:
        """Ingest a single document and index its chunks."""
        normalized_doc_id = self._normalize_doc_id(doc_id)
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            raise ValueError("document_text_required")

        chunks = self._split_chunks(
            normalized_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        created_at = _utc_iso()
        common_meta = {
            "doc_id": normalized_doc_id,
            "source": str(source or normalized_doc_id),
            "tags": list(tags or []),
            "ingested_at": created_at,
        }
        if metadata:
            common_meta.update({k: v for k, v in metadata.items() if k not in {"doc_id", "chunk_index"}})

        # Replace previous chunks for the same document to keep index clean.
        self.delete_document(normalized_doc_id)

        indexed = 0
        for idx, chunk in enumerate(chunks):
            vec = self._embedding_engine.embed_text_sync(chunk)
            entry_meta = {
                **common_meta,
                "chunk_index": idx,
                "chunk_total": len(chunks),
                "chunk_size": len(chunk),
                "text": chunk,
                "snippet": chunk[:220],
            }
            self._vector_store.upsert_sync(
                entry_id=self._entry_id(normalized_doc_id, idx),
                vector=vec,
                entry_type=self.ENTRY_TYPE,
                metadata=entry_meta,
            )
            indexed += 1

        return {
            "doc_id": normalized_doc_id,
            "source": common_meta["source"],
            "chunks_indexed": indexed,
            "chunk_size": max(120, int(chunk_size or self._default_chunk_size)),
            "chunk_overlap": max(0, int(chunk_overlap if chunk_overlap is not None else self._default_chunk_overlap)),
            "ingested_at": created_at,
        }

    def ingest_bulk(
        self,
        documents: list[dict[str, Any]],
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> dict[str, Any]:
        """Bulk ingest documents."""
        ok: list[dict[str, Any]] = []
        failed: list[dict[str, str]] = []
        for idx, item in enumerate(documents or []):
            doc_id = str(item.get("doc_id") or item.get("id") or f"doc_{idx + 1}")
            text = str(item.get("text") or item.get("content") or "")
            try:
                result = self.ingest_document(
                    doc_id=doc_id,
                    text=text,
                    source=item.get("source"),
                    tags=item.get("tags"),
                    metadata=item.get("metadata"),
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                ok.append(result)
            except Exception as exc:
                failed.append({"doc_id": doc_id, "error": str(exc)})
        return {"indexed": ok, "failed": failed, "count_indexed": len(ok), "count_failed": len(failed)}

    def search(
        self,
        *,
        query: str,
        limit: int = 5,
        threshold: float | None = None,
        doc_id: str | None = None,
    ) -> dict[str, Any]:
        """Semantic retrieval across indexed RAG documents."""
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            return {"query": "", "results": [], "count": 0}

        qvec = self._embedding_engine.embed_text_sync(normalized_query)
        effective_threshold = self._default_threshold if threshold is None else max(0.0, min(1.0, float(threshold)))
        raw_hits = self._vector_store.search_similar_sync(
            query_vector=qvec,
            entry_type=self.ENTRY_TYPE,
            limit=max(10, int(limit) * 4),
            threshold=effective_threshold,
        )

        normalized_doc_id = self._normalize_doc_id(doc_id) if doc_id else None
        results: list[dict[str, Any]] = []
        for hit in raw_hits:
            md = hit.metadata or {}
            hit_doc_id = str(md.get("doc_id", ""))
            if normalized_doc_id and hit_doc_id != normalized_doc_id:
                continue
            results.append(
                {
                    "entry_id": hit.id,
                    "doc_id": hit_doc_id,
                    "source": md.get("source"),
                    "chunk_index": md.get("chunk_index"),
                    "chunk_total": md.get("chunk_total"),
                    "score": round(float(hit.similarity), 6),
                    "text": str(md.get("text", "")),
                    "snippet": str(md.get("snippet", "")),
                    "tags": md.get("tags", []),
                    "ingested_at": md.get("ingested_at"),
                }
            )
            if len(results) >= int(limit):
                break

        return {
            "query": normalized_query,
            "threshold": effective_threshold,
            "count": len(results),
            "results": results,
        }

    def list_documents(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """List indexed documents with chunk counts."""
        entries = self._run_async(self._vector_store.get_by_type(self.ENTRY_TYPE, limit=max(200, int(limit) * 50)))
        grouped: dict[str, dict[str, Any]] = {}
        for entry in entries:
            md = entry.metadata or {}
            doc_id = str(md.get("doc_id", "")).strip()
            if not doc_id:
                continue
            info = grouped.setdefault(
                doc_id,
                {
                    "doc_id": doc_id,
                    "source": md.get("source"),
                    "chunk_count": 0,
                    "tags": md.get("tags", []),
                    "ingested_at": md.get("ingested_at"),
                    "updated_at": entry.updated_at,
                },
            )
            info["chunk_count"] += 1
            info["updated_at"] = max(str(info.get("updated_at", "")), str(entry.updated_at))
            if not info.get("source") and md.get("source"):
                info["source"] = md.get("source")

        docs = list(grouped.values())
        docs.sort(key=lambda d: str(d.get("updated_at", "")), reverse=True)
        return docs[: max(1, int(limit))]

    def delete_document(self, doc_id: str) -> dict[str, Any]:
        """Delete all chunks of a document."""
        normalized_doc_id = self._normalize_doc_id(doc_id)
        entries = self._run_async(self._vector_store.get_by_type(self.ENTRY_TYPE, limit=100000))
        deleted = 0
        for entry in entries:
            md = entry.metadata or {}
            if str(md.get("doc_id", "")) != normalized_doc_id:
                continue
            if self._run_async(self._vector_store.delete(entry.id)):
                deleted += 1
        return {"doc_id": normalized_doc_id, "deleted_chunks": deleted}

    def stats(self) -> dict[str, Any]:
        """Return RAG status and counts."""
        all_stats = self._run_async(self._vector_store.stats())
        docs = self.list_documents(limit=5000)
        by_type = all_stats.get("by_type", {}) if isinstance(all_stats, dict) else {}
        return {
            "ok": True,
            "entry_type": self.ENTRY_TYPE,
            "chunk_count": int(by_type.get(self.ENTRY_TYPE, 0)),
            "document_count": len(docs),
            "default_chunk_size": self._default_chunk_size,
            "default_chunk_overlap": self._default_chunk_overlap,
            "default_threshold": self._default_threshold,
            "vector_store": all_stats if isinstance(all_stats, dict) else {},
            "timestamp": time.time(),
        }
