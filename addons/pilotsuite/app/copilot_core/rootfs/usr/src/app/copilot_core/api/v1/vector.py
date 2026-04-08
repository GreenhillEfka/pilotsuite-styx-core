"""Vector Store API endpoints.

Provides REST API for:
- POST /api/v1/embeddings - Generate and store embeddings
- GET /api/v1/similar/{entity_id} - Find similar entities
- GET /api/v1/vectors - List vectors
- GET /api/v1/vectors/{id} - Get specific vector
- DELETE /api/v1/vectors/{id} - Delete vector
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.validation import validate_json
from copilot_core.api.v1.schemas import EmbeddingRequest, SimilarityRequest, BulkEmbeddingRequest
from copilot_core.vector_store.store import get_vector_store, VectorStore, VectorStoreConfig
from copilot_core.vector_store.embeddings import get_embedding_engine, EmbeddingEngine

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("vector", __name__, url_prefix="/vector")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


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
        return jsonify({"ok": False, "error": str(e)}), 500


def _create_entity_embedding(entity_id: str, data: dict[str, Any]):
    """Create embedding for an entity."""
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        entry = loop.run_until_complete(
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
        
    finally:
        loop.close()


def _create_user_preference_embedding(user_id: str, data: dict[str, Any]):
    """Create embedding for user preferences."""
    import asyncio
    
    preferences = data.get("preferences", {})
    if not preferences:
        return jsonify({
            "ok": False,
            "error": "Missing required field: preferences",
        }), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        entry = loop.run_until_complete(
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
        
    finally:
        loop.close()


def _create_pattern_embedding(pattern_id: str, data: dict[str, Any]):
    """Create embedding for a pattern."""
    import asyncio
    
    entities = data.get("entities", [])
    if not entities:
        return jsonify({
            "ok": False,
            "error": "Missing required field: entities",
        }), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        entry = loop.run_until_complete(
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
        
    finally:
        loop.close()


# ==================== Similarity Search ====================

@bp.get("/similar/<path:entry_id>")
def find_similar(entry_id: str):
    """Find similar entities.
    
    Query params:
    - type: Filter by type (entity, user_preference, pattern)
    - limit: Max results (default 10)
    - threshold: Min similarity threshold (default 0.7)
    """
    import asyncio
    
    try:
        entry_type = request.args.get("type")
        limit = min(int(request.args.get("limit", "10")), 100)
        threshold = float(request.args.get("threshold", "0.7"))
        
        # Get the entry's vector
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Normalize entry_id (add prefix if needed)
        if not entry_id.startswith(("entity:", "user_pref:", "pattern:")):
            # Try to find by type or default to entity
            if entry_type == "user_preference":
                lookup_id = f"user_pref:{entry_id}"
            elif entry_type == "pattern":
                lookup_id = f"pattern:{entry_id}"
            else:
                lookup_id = f"entity:{entry_id}"
        else:
            lookup_id = entry_id
            
        entry = loop.run_until_complete(_store().get(lookup_id))
        
        if not entry:
            return jsonify({
                "ok": False,
                "error": f"Entry not found: {entry_id}",
            }), 404
            
        # Search for similar
        results = loop.run_until_complete(
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
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        _LOGGER.exception("Failed to find similar entries")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        loop.close()


# ==================== Vector Management ====================

@bp.get("/vectors")
def list_vectors():
    """List vectors.
    
    Query params:
    - type: Filter by type (entity, user_preference, pattern)
    - limit: Max results (default 50)
    """
    import asyncio
    
    try:
        entry_type = request.args.get("type")
        limit = min(int(request.args.get("limit", "50")), 200)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if entry_type:
            entries = loop.run_until_complete(
                _store().get_by_type(entry_type, limit)
            )
        else:
            # Get all types
            entries = []
            for t in ["entity", "user_preference", "pattern"]:
                entries.extend(
                    loop.run_until_complete(_store().get_by_type(t, limit))
                )
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
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        loop.close()


@bp.get("/vectors/<path:entry_id>")
def get_vector(entry_id: str):
    """Get a specific vector."""
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Normalize entry_id
        if not entry_id.startswith(("entity:", "user_pref:", "pattern:")):
            # Try different prefixes
            for prefix in ["entity:", "user_pref:", "pattern:"]:
                entry = loop.run_until_complete(_store().get(f"{prefix}{entry_id}"))
                if entry:
                    break
            else:
                entry = None
        else:
            entry = loop.run_until_complete(_store().get(entry_id))
            
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
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        loop.close()


@bp.delete("/vectors/<path:entry_id>")
def delete_vector(entry_id: str):
    """Delete a vector."""
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Normalize entry_id
        if not entry_id.startswith(("entity:", "user_pref:", "pattern:")):
            for prefix in ["entity:", "user_pref:", "pattern:"]:
                deleted = loop.run_until_complete(_store().delete(f"{prefix}{entry_id}"))
                if deleted:
                    return jsonify({"ok": True, "deleted": f"{prefix}{entry_id}"})
            return jsonify({
                "ok": False,
                "error": f"Entry not found: {entry_id}",
            }), 404
        else:
            deleted = loop.run_until_complete(_store().delete(entry_id))
            if not deleted:
                return jsonify({
                    "ok": False,
                    "error": f"Entry not found: {entry_id}",
                }), 404
                
        return jsonify({"ok": True, "deleted": entry_id})
        
    except Exception as e:
        _LOGGER.exception("Failed to delete vector")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        loop.close()


# ==================== Stats ====================

@bp.get("/stats")
def vector_stats():
    """Get vector store statistics."""
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        stats = loop.run_until_complete(_store().stats())
        
        return jsonify({
            "ok": True,
            "stats": stats,
        })
        
    except Exception as e:
        _LOGGER.exception("Failed to get vector stats")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        loop.close()


@bp.delete("/vectors")
def clear_vectors():
    """Clear vectors by type.
    
    Query params:
    - type: Only clear entries of this type (optional)
    """
    import asyncio
    
    try:
        entry_type = request.args.get("type")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        count = loop.run_until_complete(_store().clear(entry_type))
        
        return jsonify({
            "ok": True,
            "deleted_count": count,
            "type": entry_type or "all",
        })
        
    except Exception as e:
        _LOGGER.exception("Failed to clear vectors")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        loop.close()


# ==================== Bulk Operations ====================

@bp.post("/embeddings/bulk")
@validate_json(BulkEmbeddingRequest)
def create_embeddings_bulk(body: BulkEmbeddingRequest):
    """Create multiple embeddings at once."""
    import asyncio

    try:
        entities = body.entities
        user_preferences = body.user_preferences
        patterns = body.patterns
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
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
                    
                loop.run_until_complete(
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
                    
                loop.run_until_complete(
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
                    
                loop.run_until_complete(
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
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        loop.close()


# ==================== Similarity Between Two ====================

@bp.post("/similarity")
@validate_json(SimilarityRequest)
def compute_similarity(body: SimilarityRequest):
    """Compute similarity between two entries or vectors."""
    import asyncio
    import math

    try:
        # Check for vector inputs
        if body.vector1 is not None and body.vector2 is not None:
            vec1 = body.vector1
            vec2 = body.vector2
        else:
            id1 = body.id1
            id2 = body.id2
                
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Normalize IDs
            def normalize_id(id_str):
                if not id_str.startswith(("entity:", "user_pref:", "pattern:")):
                    return f"entity:{id_str}"
                return id_str
                
            entry1 = loop.run_until_complete(_store().get(normalize_id(id1)))
            entry2 = loop.run_until_complete(_store().get(normalize_id(id2)))
            loop.close()
            
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
        return jsonify({"ok": False, "error": str(e)}), 500