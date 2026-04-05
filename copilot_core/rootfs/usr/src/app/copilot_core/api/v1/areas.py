

# ── SLICE 166: Areas API Expansion ─────────────────────────────────

bp = Blueprint("areas", __name__, url_prefix="/areas")


@bp.get("/hierarchy")
def areas_hierarchy():
    """Get area hierarchy (parent/child relationships).
    
    Returns tree structure of areas.
    """
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        manager = get_areas_manager()
        hierarchy = manager.get_hierarchy()
    except Exception as e:
        _LOGGER.warning("Failed to get areas hierarchy: %s", e)
        hierarchy = []
    
    return jsonify({
        "ok": True,
        "hierarchy": hierarchy,
        "count": len(hierarchy),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/hierarchy")
def areas_create_hierarchy():
    """Create a parent/child area relationship.
    
    Requires admin token.
    
    Body:
    - parent_id: Parent area ID
    - child_id: Child area ID
    """
    auth_error = _require_admin_mutation("CREATE_AREA_HIERARCHY", "Admin token required")
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
    
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        manager = get_areas_manager()
        result = manager.create_hierarchy(parent_id=parent_id, child_id=child_id)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to create area hierarchy: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "parent_id": parent_id,
        "child_id": child_id
    })


@bp.get("/<area_id>/devices")
def areas_devices(area_id):
    """List all devices in an area.
    
    Query params:
    - limit: Max devices (default 100)
    """
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    limit = max(1, min(limit, 500))
    
    try:
        manager = get_areas_manager()
        devices = manager.get_devices(area_id=area_id, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to get area devices: %s", e)
        devices = []
    
    return jsonify({
        "ok": True,
        "area_id": area_id,
        "devices": devices,
        "count": len(devices),
        "limit": limit
    })


@bp.get("/<area_id>/entities")
def areas_entities(area_id):
    """List all entities in an area.
    
    Query params:
    - limit: Max entities (default 100)
    - domain: Filter by domain (optional)
    """
    from copilot_core.areas.manager import get_areas_manager
    
    domain = request.args.get("domain")
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    limit = max(1, min(limit, 500))
    
    try:
        manager = get_areas_manager()
        entities = manager.get_entities(area_id=area_id, domain=domain, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to get area entities: %s", e)
        entities = []
    
    return jsonify({
        "ok": True,
        "area_id": area_id,
        "entities": entities,
        "count": len(entities),
        "domain": domain,
        "limit": limit
    })


@bp.get("/<area_id>/statistics")
def areas_statistics(area_id):
    """Get statistics for an area.
    
    Returns device count, entity count, coverage info.
    """
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        manager = get_areas_manager()
        stats = manager.get_statistics(area_id=area_id)
    except Exception as e:
        _LOGGER.warning("Failed to get area statistics: %s", e)
        stats = {
            "area_id": area_id,
            "device_count": 0,
            "entity_count": 0,
            "coverage_percent": 0.0
        }
    
    return jsonify({
        "ok": True,
        "statistics": stats,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/statistics/summary")
def areas_statistics_summary():
    """Get aggregated statistics for all areas.
    
    Returns total areas, total devices, total entities, coverage summary.
    """
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        manager = get_areas_manager()
        summary = manager.get_summary_statistics()
    except Exception as e:
        _LOGGER.warning("Failed to get areas summary: %s", e)
        summary = {
            "total_areas": 0,
            "total_devices": 0,
            "total_entities": 0,
            "avg_coverage_percent": 0.0
        }
    
    return jsonify({
        "ok": True,
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ── SLICE 174: Areas/Floorplan Integration ─────────────────────────────────

@bp.get("/<area_id>/floorplan")
def areas_get_floorplan(area_id):
    """Get floorplan associated with an area.
    
    Returns floorplan ID, image URL, and zone mapping for this area.
    """
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        manager = get_areas_manager()
        floorplan = manager.get_floorplan(area_id=area_id)
    except Exception as e:
        _LOGGER.warning("Failed to get area floorplan: %s", e)
        floorplan = None
    
    if not floorplan:
        return jsonify({
            "ok": False,
            "error": "No floorplan associated with this area"
        }), 404
    
    return jsonify({
        "ok": True,
        "area_id": area_id,
        "floorplan": floorplan,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.put("/<area_id>/floorplan")
def areas_set_floorplan(area_id):
    """Associate a floorplan with an area.
    
    Requires admin token.
    
    Body:
    - floorplan_id: Floorplan to associate
    - zone_mapping: Optional {area_sub_id: floorplan_zone_id} mapping
    """
    auth_error = _require_admin_mutation("SET_AREA_FLOORPLAN", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    floorplan_id = data.get("floorplan_id")
    zone_mapping = data.get("zone_mapping", {})
    
    if not floorplan_id:
        return jsonify({
            "ok": False,
            "error": "Missing floorplan_id"
        }), 400
    
    from copilot_core.areas.manager import get_areas_manager
    
    try:
        manager = get_areas_manager()
        result = manager.set_floorplan(area_id=area_id, floorplan_id=floorplan_id, zone_mapping=zone_mapping)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to set area floorplan: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "area_id": area_id,
        "floorplan_id": floorplan_id,
        "zone_mapping": zone_mapping
    })
