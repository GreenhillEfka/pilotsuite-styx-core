

# ── SLICE 168: Labels API Expansion ─────────────────────────────────

bp = Blueprint("labels", __name__, url_prefix="/labels")


@bp.put("/<label_id>/color")
def labels_set_color(label_id):
    """Set color for a label.
    
    Requires admin token.
    
    Body:
    - color: Color code (hex or named color)
    """
    auth_error = _require_admin_mutation("SET_LABEL_COLOR", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    color = data.get("color")
    
    if not color:
        return jsonify({
            "ok": False,
            "error": "Missing color"
        }), 400
    
    from copilot_core.labels.manager import get_labels_manager
    
    try:
        manager = get_labels_manager()
        result = manager.set_color(label_id=label_id, color=color)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to set label color: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "label_id": label_id,
        "color": color
    })


@bp.post("/<label_id>/assign")
def labels_assign(label_id):
    """Assign a label to an entity or device.
    
    Body:
    - target_type: entity|device
    - target_id: ID of the entity or device
    """
    data = request.get_json() or {}
    target_type = data.get("target_type")
    target_id = data.get("target_id")
    
    if not target_type or not target_id:
        return jsonify({
            "ok": False,
            "error": "Missing target_type or target_id"
        }), 400
    
    from copilot_core.labels.manager import get_labels_manager
    
    try:
        manager = get_labels_manager()
        result = manager.assign(label_id=label_id, target_type=target_type, target_id=target_id)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to assign label: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "label_id": label_id,
        "target_type": target_type,
        "target_id": target_id
    })


@bp.delete("/<label_id>/assign")
def labels_unassign(label_id):
    """Remove a label assignment.
    
    Body:
    - target_type: entity|device
    - target_id: ID of the entity or device
    """
    data = request.get_json() or {}
    target_type = data.get("target_type")
    target_id = data.get("target_id")
    
    if not target_type or not target_id:
        return jsonify({
            "ok": False,
            "error": "Missing target_type or target_id"
        }), 400
    
    from copilot_core.labels.manager import get_labels_manager
    
    try:
        manager = get_labels_manager()
        result = manager.unassign(label_id=label_id, target_type=target_type, target_id=target_id)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to unassign label: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "label_id": label_id,
        "target_type": target_type,
        "target_id": target_id
    })


@bp.get("/<label_id>/assignments")
def labels_assignments(label_id):
    """Get all assignments for a label.
    
    Returns list of entities and devices with this label.
    """
    from copilot_core.labels.manager import get_labels_manager
    
    try:
        manager = get_labels_manager()
        assignments = manager.get_assignments(label_id=label_id)
    except Exception as e:
        _LOGGER.warning("Failed to get label assignments: %s", e)
        assignments = []
    
    return jsonify({
        "ok": True,
        "label_id": label_id,
        "assignments": assignments,
        "count": len(assignments),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/filter")
def labels_filter():
    """Filter entities/devices by label.
    
    Query params:
    - label_ids: Comma-separated label IDs
    - target_type: entity|device|all (default: all)
    - limit: Max results (default 100)
    """
    from copilot_core.labels.manager import get_labels_manager
    
    label_ids = request.args.get("label_ids")
    target_type = request.args.get("target_type", "all")
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    limit = max(1, min(limit, 500))
    
    label_list = [l.strip() for l in label_ids.split(",")] if label_ids else []
    
    try:
        manager = get_labels_manager()
        results = manager.filter(label_ids=label_list, target_type=target_type, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to filter by labels: %s", e)
        results = []
    
    return jsonify({
        "ok": True,
        "results": results,
        "count": len(results),
        "label_ids": label_list,
        "target_type": target_type,
        "limit": limit
    })


@bp.get("/analytics")
def labels_analytics():
    """Get label usage analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.labels.manager import get_labels_manager
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        manager = get_labels_manager()
        analytics = manager.get_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get labels analytics: %s", e)
        analytics = {
            "total_labels": 0,
            "total_assignments": 0,
            "most_used_labels": [],
            "avg_assignments_per_label": 0.0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
