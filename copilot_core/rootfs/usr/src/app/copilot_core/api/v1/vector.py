"""Vector Store API endpoints.

Provides REST API for:
- POST /api/v1/embeddings - Generate and store embeddings
- GET /api/v1/similar/{entity_id} - Find similar entities
- GET /api/v1/vectors - List vectors
- GET /api/v1/vectors/{id} - Get specific vector
- DELETE /api/v1/vectors/{id} - Delete vector
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.validation import validate_json
from copilot_core.api.v1.schemas import EmbeddingRequest, SimilarityRequest, BulkEmbeddingRequest
from copilot_core.api.api_errors import unauthorized, bad_request, internal_error, not_found
from copilot_core.vector_store.store import get_vector_store, VectorStore, VectorStoreConfig
from copilot_core.vector_store.embeddings import get_embedding_engine, EmbeddingEngine

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("vector", __name__, url_prefix="/vector")

from copilot_core.api.security import validate_token as _validate_token


def _run_async(coro, timeout: int = 10):
    """Run async coroutine from sync Flask context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, asyncio.wait_for(coro, timeout=timeout))
            return future.result(timeout=timeout + 2)

    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return unauthorized("Valid X-Auth-Token or Bearer token required", req=request)


def _store() -> VectorStore:
    """Get the vector store singleton."""
    return get_vector_store()


def _engine() -> EmbeddingEngine:
    """Get the embedding engine singleton."""
    return get_embedding_engine()


# ==================== Embeddings ====================

@bp.post("/embeddings")
@validate_json(EmbeddingRequest)
def create_embedding(body: EmbeddingRequest):
    """Generate and store an embedding."""
    try:
        data = body.model_dump(exclude_none=True)
        entry_id = body.id

        if body.type == "entity":
            return _create_entity_embedding(entry_id, data)
        elif body.type == "user_preference":
            return _create_user_preference_embedding(entry_id, data)
        else:
            return _create_pattern_embedding(entry_id, data)

    except Exception as e:
        _LOGGER.exception("Failed to create embedding")
        return internal_error("Failed to create embedding", str(e))


def _create_entity_embedding(entity_id: str, data: dict[str, Any]):
    """Create embedding for an entity."""
    entry = _run_async(
        _store().store_entity_embedding(
            entity_id=entity_id,
            domain=data.get("domain"),
            area=data.get("area"),
            capabilities=data.get("capabilities"),
            tags=data.get("tags"),
            state=data.get("state"),
            metadata=data.get("metadata"),
        )
    )

    return jsonify({
        "ok": True,
        "entry": {
            "id": entry.id,
            "type": entry.entry_type,
            "created_at": entry.created_at,
            "metadata": entry.metadata,
        },
    }), 201


def _create_user_preference_embedding(user_id: str, data: dict[str, Any]):
    """Create embedding for user preferences."""
    preferences = data.get("preferences", {})
    if not preferences:
        return jsonify({
            "ok": False,
            "error": "Missing required field: preferences",
        }), 400

    entry = _run_async(
        _store().store_user_preference_embedding(
            user_id=user_id,
            preferences=preferences,
            metadata=data.get("metadata"),
        )
    )

    return jsonify({
        "ok": True,
        "entry": {
            "id": entry.id,
            "type": entry.entry_type,
            "created_at": entry.created_at,
            "metadata": entry.metadata,
        },
    }), 201


def _create_pattern_embedding(pattern_id: str, data: dict[str, Any]):
    """Create embedding for a pattern."""
    entities = data.get("entities", [])
    if not entities:
        return jsonify({
            "ok": False,
            "error": "Missing required field: entities",
        }), 400

    entry = _run_async(
        _store().store_pattern_embedding(
            pattern_id=pattern_id,
            pattern_type=data.get("pattern_type", "learned"),
            entities=entities,
            conditions=data.get("conditions"),
            confidence=data.get("confidence", 0.0),
            metadata=data.get("metadata"),
        )
    )

    return jsonify({
        "ok": True,
        "entry": {
            "id": entry.id,
            "type": entry.entry_type,
            "created_at": entry.created_at,
            "metadata": entry.metadata,
        },
    }), 201


# ==================== Similarity Search ====================

@bp.get("/similar/<path:entry_id>")
def find_similar(entry_id: str):
    """Find similar entities.

    Query params:
    - type: Filter by type (entity, user_preference, pattern)
    - limit: Max results (default 10)
    - threshold: Min similarity threshold (default 0.7)
    """
    try:
        entry_type = request.args.get("type")
        limit = min(int(request.args.get("limit", "10")), 100)
        threshold = float(request.args.get("threshold", "0.7"))

        # Normalize entry_id (add prefix if needed)
        if not entry_id.startswith(("entity:", "user_pref:", "pattern:")):
            if entry_type == "user_preference":
                lookup_id = f"user_pref:{entry_id}"
            elif entry_type == "pattern":
                lookup_id = f"pattern:{entry_id}"
            else:
                lookup_id = f"entity:{entry_id}"
        else:
            lookup_id = entry_id

        entry = _run_async(_store().get(lookup_id))

        if not entry:
            return jsonify({
                "ok": False,
                "error": f"Entry not found: {entry_id}",
            }), 404

        # Search for similar
        results = _run_async(
            _store().search_similar(
                query_vector=entry.vector,
                entry_type=entry_type,
                limit=limit,
                threshold=threshold,
                exclude_ids=[lookup_id],
            )
        )

        return jsonify({
            "ok": True,
            "query_id": lookup_id,
            "query_type": entry.entry_type,
            "results": [
                {
                    "id": r.id,
                    "similarity": round(r.similarity, 4),
                    "type": r.entry_type,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "count": len(results),
        })

    except ValueError as e:
        return bad_request("Validation failed", details={"detail": str(e)})
    except Exception as e:
        _LOGGER.exception("Failed to find similar entries")
        return internal_error("Failed to find similar entries", str(e))


# ==================== Vector Management ====================

@bp.get("/vectors")
def list_vectors():
    """List vectors.

    Query params:
    - type: Filter by type (entity, user_preference, pattern)
    - limit: Max results (default 50)
    """
    try:
        entry_type = request.args.get("type")
        limit = min(int(request.args.get("limit", "50")), 200)

        if entry_type:
            entries = _run_async(_store().get_by_type(entry_type, limit))
        else:
            entries = []
            for t in ["entity", "user_preference", "pattern"]:
                entries.extend(_run_async(_store().get_by_type(t, limit)))
            entries = entries[:limit]

        return jsonify({
            "ok": True,
            "entries": [
                {
                    "id": e.id,
                    "type": e.entry_type,
                    "created_at": e.created_at,
                    "updated_at": e.updated_at,
                    "metadata": e.metadata,
                }
                for e in entries
            ],
            "count": len(entries),
        })

    except Exception as e:
        _LOGGER.exception("Failed to list vectors")
        return internal_error("Failed to list vectors", str(e))


@bp.get("/vectors/<path:entry_id>")
def get_vector(entry_id: str):
    """Get a specific vector."""
    try:
        # Normalize entry_id
        if not entry_id.startswith(("entity:", "user_pref:", "pattern:")):
            entry = None
            for prefix in ["entity:", "user_pref:", "pattern:"]:
                entry = _run_async(_store().get(f"{prefix}{entry_id}"))
                if entry:
                    break
        else:
            entry = _run_async(_store().get(entry_id))

        if not entry:
            return jsonify({
                "ok": False,
                "error": f"Entry not found: {entry_id}",
            }), 404

        return jsonify({
            "ok": True,
            "entry": {
                "id": entry.id,
                "type": entry.entry_type,
                "vector": entry.vector,
                "dimension": len(entry.vector),
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
                "metadata": entry.metadata,
            },
        })

    except Exception as e:
        _LOGGER.exception("Failed to get vector")
        return internal_error("Failed to get vector", str(e))


@bp.delete("/vectors/<path:entry_id>")
def delete_vector(entry_id: str):
    """Delete a vector."""
    try:
        # Normalize entry_id
        if not entry_id.startswith(("entity:", "user_pref:", "pattern:")):
            for prefix in ["entity:", "user_pref:", "pattern:"]:
                deleted = _run_async(_store().delete(f"{prefix}{entry_id}"))
                if deleted:
                    return jsonify({"ok": True, "deleted": f"{prefix}{entry_id}"})
            return jsonify({
                "ok": False,
                "error": f"Entry not found: {entry_id}",
            }), 404
        else:
            deleted = _run_async(_store().delete(entry_id))
            if not deleted:
                return jsonify({
                    "ok": False,
                    "error": f"Entry not found: {entry_id}",
                }), 404

        return jsonify({"ok": True, "deleted": entry_id})

    except Exception as e:
        _LOGGER.exception("Failed to delete vector")
        return internal_error("Failed to delete vector", str(e))


# ==================== Stats ====================

@bp.get("/stats")
def vector_stats():
    """Get vector store statistics."""
    try:
        stats = _run_async(_store().stats())

        return jsonify({
            "ok": True,
            "stats": stats,
        })

    except Exception as e:
        _LOGGER.exception("Failed to get vector stats")
        return internal_error("Failed to get vector stats", str(e))


@bp.delete("/vectors")
def clear_vectors():
    """Clear vectors by type.

    Query params:
    - type: Only clear entries of this type (optional)
    """
    try:
        entry_type = request.args.get("type")
        count = _run_async(_store().clear(entry_type))

        return jsonify({
            "ok": True,
            "deleted_count": count,
            "type": entry_type or "all",
        })

    except Exception as e:
        _LOGGER.exception("Failed to clear vectors")
        return internal_error("Failed to clear vectors", str(e))


# ==================== Bulk Operations ====================

@bp.post("/embeddings/bulk")
@validate_json(BulkEmbeddingRequest)
def create_embeddings_bulk(body: BulkEmbeddingRequest):
    """Create multiple embeddings at once."""
    try:
        entities = body.entities
        user_preferences = body.user_preferences
        patterns = body.patterns

        results = {
            "entities": {"created": 0, "failed": 0},
            "user_preferences": {"created": 0, "failed": 0},
            "patterns": {"created": 0, "failed": 0},
        }

        # Process entities
        for entity in entities:
            try:
                entity_id = entity.get("id") or entity.get("entity_id")
                if not entity_id:
                    results["entities"]["failed"] += 1
                    continue

                _run_async(
                    _store().store_entity_embedding(
                        entity_id=entity_id,
                        domain=entity.get("domain"),
                        area=entity.get("area"),
                        capabilities=entity.get("capabilities"),
                        tags=entity.get("tags"),
                        state=entity.get("state"),
                        metadata=entity.get("metadata"),
                    )
                )
                results["entities"]["created"] += 1
            except Exception as e:
                _LOGGER.warning("Failed to create entity embedding: %s", e)
                results["entities"]["failed"] += 1

        # Process user preferences
        for pref in user_preferences:
            try:
                user_id = pref.get("id") or pref.get("user_id")
                preferences = pref.get("preferences", {})
                if not user_id or not preferences:
                    results["user_preferences"]["failed"] += 1
                    continue

                _run_async(
                    _store().store_user_preference_embedding(
                        user_id=user_id,
                        preferences=preferences,
                        metadata=pref.get("metadata"),
                    )
                )
                results["user_preferences"]["created"] += 1
            except Exception as e:
                _LOGGER.warning("Failed to create user preference embedding: %s", e)
                results["user_preferences"]["failed"] += 1

        # Process patterns
        for pattern in patterns:
            try:
                pattern_id = pattern.get("id") or pattern.get("pattern_id")
                entities_list = pattern.get("entities", [])
                if not pattern_id or not entities_list:
                    results["patterns"]["failed"] += 1
                    continue

                _run_async(
                    _store().store_pattern_embedding(
                        pattern_id=pattern_id,
                        pattern_type=pattern.get("pattern_type", "learned"),
                        entities=entities_list,
                        conditions=pattern.get("conditions"),
                        confidence=pattern.get("confidence", 0.0),
                        metadata=pattern.get("metadata"),
                    )
                )
                results["patterns"]["created"] += 1
            except Exception as e:
                _LOGGER.warning("Failed to create pattern embedding: %s", e)
                results["patterns"]["failed"] += 1

        return jsonify({
            "ok": True,
            "results": results,
        }), 201

    except Exception as e:
        _LOGGER.exception("Failed to create bulk embeddings")
        return internal_error("Failed to create bulk embeddings", str(e))


# ==================== Similarity Between Two ====================

@bp.post("/similarity")
@validate_json(SimilarityRequest)
def compute_similarity(body: SimilarityRequest):
    """Compute similarity between two entries or vectors."""
    try:
        # Check for vector inputs
        if body.vector1 is not None and body.vector2 is not None:
            vec1 = body.vector1
            vec2 = body.vector2
        else:
            id1 = body.id1
            id2 = body.id2

            # Normalize IDs
            def normalize_id(id_str):
                if not id_str.startswith(("entity:", "user_pref:", "pattern:")):
                    return f"entity:{id_str}"
                return id_str

            entry1 = _run_async(_store().get(normalize_id(id1)))
            entry2 = _run_async(_store().get(normalize_id(id2)))

            if not entry1:
                return jsonify({"ok": False, "error": f"Entry not found: {id1}"}), 404
            if not entry2:
                return jsonify({"ok": False, "error": f"Entry not found: {id2}"}), 404

            vec1 = entry1.vector
            vec2 = entry2.vector

        # Compute cosine similarity
        if len(vec1) != len(vec2):
            return jsonify({
                "ok": False,
                "error": f"Vector dimensions don't match: {len(vec1)} vs {len(vec2)}",
            }), 400

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            similarity = 0.0
        else:
            similarity = dot_product / (magnitude1 * magnitude2)

        return jsonify({
            "ok": True,
            "similarity": round(similarity, 4),
            "dimension": len(vec1),
        })

    except Exception as e:
        _LOGGER.exception("Failed to compute similarity")
        return internal_error("Failed to compute similarity", str(e))


# ── SLICE 143: Vector API Expansion ─────────────────────────────────

@bp.get("/collections")
def vector_collections():
    """List all vector collections.
    
    Returns:
    - collections: List of collection names
    - count: Total number of collections
    """
    from copilot_core.vector.store import get_vector_store
    
    try:
        store = get_vector_store()
        collections = store.list_collections()
    except Exception as e:
        _LOGGER.warning("Failed to list collections: %s", e)
        collections = []
    
    return jsonify({
        "ok": True,
        "collections": collections,
        "count": len(collections),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/collections/<collection_name>")
def create_vector_collection(collection_name):
    """Create a new vector collection.
    
    Requires admin token.
    
    Body (optional):
    - dimension: Vector dimension (default: 384)
    - metric: Similarity metric (cosine|dot|euclidean, default: cosine)
    """
    auth_error = _require_admin_mutation("CREATE_VECTOR_COLLECTION", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    dimension = data.get("dimension", 384)
    metric = data.get("metric", "cosine")
    
    from copilot_core.vector.store import get_vector_store
    
    try:
        store = get_vector_store()
        store.create_collection(
            name=collection_name,
            dimension=dimension,
            metric=metric
        )
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to create collection: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "collection": collection_name,
        "dimension": dimension,
        "metric": metric
    })


@bp.delete("/collections/<collection_name>")
def delete_vector_collection(collection_name):
    """Delete a vector collection.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("DELETE_VECTOR_COLLECTION", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.vector.store import get_vector_store
    
    try:
        store = get_vector_store()
        store.delete_collection(name=collection_name)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to delete collection: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "collection": collection_name
    })


@bp.post("/batch/upsert")
def vector_batch_upsert():
    """Batch upsert multiple documents.
    
    Body:
    - collection: Collection name
    - documents: List of {id, vector, metadata}
    """
    data = request.get_json() or {}
    collection = data.get("collection")
    documents = data.get("documents", [])
    
    if not collection:
        return jsonify({
            "ok": False,
            "error": "Missing collection name"
        }), 400
    
    if not documents or len(documents) > 1000:
        return jsonify({
            "ok": False,
            "error": "Documents required (max 1000 per batch)"
        }), 400
    
    from copilot_core.vector.store import get_vector_store
    
    try:
        store = get_vector_store()
        result = store.batch_upsert(collection=collection, documents=documents)
        success = True
        inserted = result.get("inserted", len(documents))
    except Exception as e:
        _LOGGER.warning("Failed to batch upsert: %s", e)
        success = False
        inserted = 0
    
    return jsonify({
        "ok": success,
        "collection": collection,
        "inserted": inserted,
        "total": len(documents)
    })
