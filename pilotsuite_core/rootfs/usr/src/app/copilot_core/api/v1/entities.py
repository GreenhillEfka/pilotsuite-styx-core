

# ── SLICE 164: Entities API Expansion ─────────────────────────────────
from flask import Blueprint

bp = Blueprint("entities", __name__, url_prefix="/entities")


@bp.post("/bulk/update")
def entities_bulk_update():
    """Bulk update multiple entities.
    
    Requires admin token.
    
    Body:
    - entities: List of {entity_id, updates}
    """
    auth_error = _require_admin_mutation("BULK_UPDATE_ENTITIES", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    entities = data.get("entities", [])
    
    if not entities or len(entities) > 500:
        return jsonify({
            "ok": False,
            "error": "Entities required (max 500 per batch)"
        }), 400
    
    from copilot_core.entities.manager import get_entities_manager
    
    try:
        manager = get_entities_manager()
        result = manager.bulk_update(entities=entities)
        success = result.get("success", False)
        updated = result.get("updated_count", 0)
        failed = result.get("failed_count", 0)
    except Exception as e:
        _LOGGER.warning("Failed to bulk update entities: %s", e)
        success = False
        updated = 0
        failed = len(entities)
    
    return jsonify({
        "ok": success,
        "updated": updated,
        "failed": failed,
        "total": len(entities)
    })


@bp.get("/<entity_id>/history")
def entities_history(entity_id):
    """Get state history for an entity.
    
    Query params:
    - hours: Time range (default 24)
    - limit: Max entries (default 100)
    """
    from copilot_core.entities.manager import get_entities_manager
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    hours = max(1, min(hours, 720))
    limit = max(1, min(limit, 1000))
    
    try:
        manager = get_entities_manager()
        history = manager.get_history(entity_id=entity_id, hours=hours, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to get entity history: %s", e)
        history = []
    
    return jsonify({
        "ok": True,
        "entity_id": entity_id,
        "history": history,
        "count": len(history),
        "hours": hours,
        "limit": limit
    })


@bp.get("/<entity_id>/statistics")
def entities_statistics(entity_id):
    """Get statistics for an entity.
    
    Query params:
    - days: Days to analyze (default 7)
    """
    from copilot_core.entities.manager import get_entities_manager
    
    try:
        days = int(request.args.get("days", "7"))
    except (ValueError, TypeError):
        days = 7
    
    days = max(1, min(days, 90))
    
    try:
        manager = get_entities_manager()
        stats = manager.get_statistics(entity_id=entity_id, days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get entity statistics: %s", e)
        stats = {
            "entity_id": entity_id,
            "state_changes": 0,
            "avg_state_duration": 0.0,
            "most_common_state": None,
            "change_frequency": 0.0
        }
    
    return jsonify({
        "ok": True,
        "statistics": stats,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/relationships")
def entities_relationships():
    """Get entity relationships.
    
    Query params:
    - entity_id: Specific entity (optional, all if omitted)
    - type: parent|child|linked (optional, all if omitted)
    """
    from copilot_core.entities.manager import get_entities_manager
    
    entity_id = request.args.get("entity_id")
    rel_type = request.args.get("type")
    
    try:
        manager = get_entities_manager()
        relationships = manager.get_relationships(entity_id=entity_id, rel_type=rel_type)
    except Exception as e:
        _LOGGER.warning("Failed to get entity relationships: %s", e)
        relationships = []
    
    return jsonify({
        "ok": True,
        "relationships": relationships,
        "count": len(relationships),
        "entity_id": entity_id,
        "type": rel_type,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/statistics/summary")
def entities_statistics_summary():
    """Get aggregated entity statistics.
    
    Query params:
    - days: Days to analyze (default 7)
    """
    from copilot_core.entities.manager import get_entities_manager
    
    try:
        days = int(request.args.get("days", "7"))
    except (ValueError, TypeError):
        days = 7
    
    days = max(1, min(days, 90))
    
    try:
        manager = get_entities_manager()
        summary = manager.get_statistics_summary(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get entity statistics summary: %s", e)
        summary = {
            "total_entities": 0,
            "active_entities": 0,
            "total_state_changes": 0,
            "avg_changes_per_entity": 0.0
        }
    
    return jsonify({
        "ok": True,
        "summary": summary,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
