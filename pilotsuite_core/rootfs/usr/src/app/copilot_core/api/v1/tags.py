

# ── SLICE 159: Tags API Expansion ─────────────────────────────────
from flask import Blueprint

bp = Blueprint("tags", __name__, url_prefix="/tags")


@bp.get("/hierarchies")
def tags_hierarchies():
    """Get tag hierarchies (parent/child relationships).
    
    Returns tree structure of tags with parent/child relationships.
    """
    from copilot_core.tags.manager import get_tags_manager
    
    try:
        manager = get_tags_manager()
        hierarchies = manager.get_hierarchies()
    except Exception as e:
        _LOGGER.warning("Failed to get tag hierarchies: %s", e)
        hierarchies = []
    
    return jsonify({
        "ok": True,
        "hierarchies": hierarchies,
        "count": len(hierarchies),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/hierarchies")
def tags_create_hierarchy():
    """Create a parent/child tag relationship.
    
    Requires admin token.
    
    Body:
    - parent_id: Parent tag ID
    - child_id: Child tag ID
    """
    auth_error = _require_admin_mutation("CREATE_TAG_HIERARCHY", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    parent_id = data.get("parent_id")
    child_id = data.get("child_id")
    
    if not parent_id or not child_id:
        return jsonify({
            "ok": False,
            "error": "Missing parent_id or child_id"
        }), 400
    
    from copilot_core.tags.manager import get_tags_manager
    
    try:
        manager = get_tags_manager()
        result = manager.create_hierarchy(parent_id=parent_id, child_id=child_id)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to create tag hierarchy: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "parent_id": parent_id,
        "child_id": child_id
    })


@bp.get("/<tag_id>/usage")
def tags_usage(tag_id):
    """Get entities that use this tag.
    
    Query params:
    - entity_type: Filter by entity type (optional)
    - limit: Max entities (default 50)
    """
    from copilot_core.tags.manager import get_tags_manager
    
    entity_type = request.args.get("entity_type")
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    limit = max(1, min(limit, 200))
    
    try:
        manager = get_tags_manager()
        usage = manager.get_tag_usage(tag_id=tag_id, entity_type=entity_type, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to get tag usage: %s", e)
        usage = []
    
    return jsonify({
        "ok": True,
        "tag_id": tag_id,
        "usage": usage,
        "count": len(usage),
        "entity_type": entity_type,
        "limit": limit
    })


@bp.post("/merge")
def tags_merge():
    """Merge multiple tags into one.
    
    Requires admin token.
    
    Body:
    - source_ids: List of tag IDs to merge
    - target_id: Target tag ID to merge into
    """
    auth_error = _require_admin_mutation("MERGE_TAGS", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    source_ids = data.get("source_ids", [])
    target_id = data.get("target_id")
    
    if not source_ids or not target_id:
        return jsonify({
            "ok": False,
            "error": "Missing source_ids or target_id"
        }), 400
    
    from copilot_core.tags.manager import get_tags_manager
    
    try:
        manager = get_tags_manager()
        result = manager.merge_tags(source_ids=source_ids, target_id=target_id)
        success = result.get("success", False)
        merged_count = result.get("merged_count", 0)
    except Exception as e:
        _LOGGER.warning("Failed to merge tags: %s", e)
        success = False
        merged_count = 0
    
    return jsonify({
        "ok": success,
        "target_id": target_id,
        "merged_count": merged_count
    })


@bp.get("/analytics")
def tags_analytics():
    """Get tag usage analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.tags.manager import get_tags_manager
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        manager = get_tags_manager()
        analytics = manager.get_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get tag analytics: %s", e)
        analytics = {
            "total_tags": 0,
            "total_usages": 0,
            "avg_tags_per_entity": 0.0,
            "popular_tags": []
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
