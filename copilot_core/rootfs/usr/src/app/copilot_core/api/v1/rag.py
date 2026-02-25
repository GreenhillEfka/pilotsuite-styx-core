"""RAG API endpoints for document indexing and retrieval."""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.rag.service import RagService

_LOGGER = logging.getLogger(__name__)

rag_bp = Blueprint("rag_api", __name__, url_prefix="/api/v1/rag")

_service: Optional[RagService] = None


def init_rag_api(service: RagService) -> None:
    """Wire RagService into blueprint globals."""
    global _service
    _service = service


def _get_service() -> RagService:
    if _service is None:
        raise RuntimeError("rag_service_not_initialized")
    return _service


@rag_bp.route("/status", methods=["GET"])
@require_token
def rag_status():
    """Return RAG service status."""
    try:
        stats = _get_service().stats()
        return jsonify({"ok": True, "rag": stats})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@rag_bp.route("/stats", methods=["GET"])
@require_token
def rag_stats():
    """Return detailed RAG stats."""
    try:
        return jsonify({"ok": True, "stats": _get_service().stats()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@rag_bp.route("/documents", methods=["GET"])
@require_token
def list_documents():
    """List indexed documents."""
    try:
        limit = int(request.args.get("limit", "200"))
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 5000))
    docs = _get_service().list_documents(limit=limit)
    return jsonify({"ok": True, "count": len(docs), "documents": docs})


@rag_bp.route("/documents", methods=["POST"])
@require_token
def ingest_document():
    """Ingest a single RAG document."""
    body = request.get_json(silent=True) or {}
    doc_id = str(body.get("doc_id") or body.get("id") or "").strip()
    text = str(body.get("text") or body.get("content") or "")
    if not doc_id:
        return jsonify({"ok": False, "error": "missing_doc_id"}), 400
    if not text.strip():
        return jsonify({"ok": False, "error": "missing_text"}), 400

    try:
        result = _get_service().ingest_document(
            doc_id=doc_id,
            text=text,
            source=body.get("source"),
            tags=body.get("tags"),
            metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None,
            chunk_size=body.get("chunk_size"),
            chunk_overlap=body.get("chunk_overlap"),
        )
        return jsonify({"ok": True, "result": result}), 201
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        _LOGGER.exception("RAG ingest failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@rag_bp.route("/documents/bulk", methods=["POST"])
@require_token
def ingest_bulk():
    """Ingest documents in bulk."""
    body = request.get_json(silent=True) or {}
    documents = body.get("documents", [])
    if not isinstance(documents, list) or not documents:
        return jsonify({"ok": False, "error": "documents_must_be_non_empty_list"}), 400

    try:
        result = _get_service().ingest_bulk(
            documents=documents,
            chunk_size=body.get("chunk_size"),
            chunk_overlap=body.get("chunk_overlap"),
        )
        status = 201 if result.get("count_failed", 0) == 0 else 207
        return jsonify({"ok": True, **result}), status
    except Exception as exc:
        _LOGGER.exception("RAG bulk ingest failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@rag_bp.route("/documents/<path:doc_id>", methods=["DELETE"])
@require_token
def delete_document(doc_id: str):
    """Delete all chunks of a document."""
    try:
        result = _get_service().delete_document(doc_id)
        return jsonify({"ok": True, **result})
    except Exception as exc:
        _LOGGER.exception("RAG delete failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@rag_bp.route("/query", methods=["POST"])
@require_token
def query_documents():
    """Semantic query over indexed documents."""
    body = request.get_json(silent=True) or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing_query"}), 400
    try:
        limit = int(body.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, 50))
    threshold = body.get("threshold")
    if threshold is not None:
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_threshold"}), 400

    try:
        result = _get_service().search(
            query=query,
            limit=limit,
            threshold=threshold,
            doc_id=body.get("doc_id"),
        )
        return jsonify({"ok": True, **result})
    except Exception as exc:
        _LOGGER.exception("RAG query failed")
        return jsonify({"ok": False, "error": str(exc)}), 500
