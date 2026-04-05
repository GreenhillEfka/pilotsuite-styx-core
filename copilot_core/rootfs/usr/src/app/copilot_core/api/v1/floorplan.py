

# ── SLICE 167: Floor Plan API Expansion ─────────────────────────────────

@bp.post("/upload")
def floorplan_upload():
    """Upload a new floor plan image.
    
    Requires admin token.
    
    Body (multipart/form-data):
    - image: Floor plan image file
    - name: Floor plan name
    - level: Floor/level number (optional)
    """
    auth_error = _require_admin_mutation("UPLOAD_FLOORPLAN", "Admin token required")
    if auth_error:
        return auth_error
    
    # Note: File upload handling would require Flask file handling
    # This is a stub for the endpoint structure
    data = request.get_json() or {}
    name = data.get("name")
    level = data.get("level", 0)
    
    if not name:
        return jsonify({
            "ok": False,
            "error": "Missing name"
        }), 400
    
    from copilot_core.floorplan.manager import get_floorplan_manager
    
    try:
        manager = get_floorplan_manager()
        result = manager.upload_floorplan(name=name, level=level)
        success = result.get("success", False)
        floorplan_id = result.get("floorplan_id")
    except Exception as e:
        _LOGGER.warning("Failed to upload floorplan: %s", e)
        success = False
        floorplan_id = None
    
    return jsonify({
        "ok": success,
        "floorplan_id": floorplan_id,
        "name": name,
        "level": level
    })


@bp.get("/<floorplan_id>/zones")
def floorplan_zones(floorplan_id):
    """Get zones mapped to a floor plan.
    
    Returns zone coordinates and placements on the floor plan.
    """
    from copilot_core.floorplan.manager import get_floorplan_manager
    
    try:
        manager = get_floorplan_manager()
        zones = manager.get_zones(floorplan_id=floorplan_id)
    except Exception as e:
        _LOGGER.warning("Failed to get floorplan zones: %s", e)
        zones = []
    
    return jsonify({
        "ok": True,
        "floorplan_id": floorplan_id,
        "zones": zones,
        "count": len(zones),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/<floorplan_id>/zones")
def floorplan_add_zone(floorplan_id):
    """Add a zone mapping to a floor plan.
    
    Requires admin token.
    
    Body:
    - zone_id: Zone ID to map
    - coordinates: {x, y, width, height} for zone placement
    """
    auth_error = _require_admin_mutation("ADD_FLOORPLAN_ZONE", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    zone_id = data.get("zone_id")
    coordinates = data.get("coordinates", {})
    
    if not zone_id:
        return jsonify({
            "ok": False,
            "error": "Missing zone_id"
        }), 400
    
    from copilot_core.floorplan.manager import get_floorplan_manager
    
    try:
        manager = get_floorplan_manager()
        result = manager.add_zone(floorplan_id=floorplan_id, zone_id=zone_id, coordinates=coordinates)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to add floorplan zone: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "floorplan_id": floorplan_id,
        "zone_id": zone_id
    })


@bp.get("/<floorplan_id>/entities")
def floorplan_entities(floorplan_id):
    """Get entities placed on a floor plan.
    
    Returns entity placements with coordinates.
    """
    from copilot_core.floorplan.manager import get_floorplan_manager
    
    try:
        manager = get_floorplan_manager()
        entities = manager.get_entities(floorplan_id=floorplan_id)
    except Exception as e:
        _LOGGER.warning("Failed to get floorplan entities: %s", e)
        entities = []
    
    return jsonify({
        "ok": True,
        "floorplan_id": floorplan_id,
        "entities": entities,
        "count": len(entities),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/<floorplan_id>/entities")
def floorplan_add_entity(floorplan_id):
    """Add an entity placement to a floor plan.
    
    Requires admin token.
    
    Body:
    - entity_id: Entity ID to place
    - coordinates: {x, y} for entity placement
    """
    auth_error = _require_admin_mutation("ADD_FLOORPLAN_ENTITY", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    entity_id = data.get("entity_id")
    coordinates = data.get("coordinates", {})
    
    if not entity_id:
        return jsonify({
            "ok": False,
            "error": "Missing entity_id"
        }), 400
    
    from copilot_core.floorplan.manager import get_floorplan_manager
    
    try:
        manager = get_floorplan_manager()
        result = manager.add_entity(floorplan_id=floorplan_id, entity_id=entity_id, coordinates=coordinates)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to add floorplan entity: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "floorplan_id": floorplan_id,
        "entity_id": entity_id
    })


@bp.get("/<floorplan_id>/export")
def floorplan_export(floorplan_id):
    """Export floor plan with overlays.
    
    Query params:
    - format: png|svg|pdf (default: png)
    - overlay: entities|zones|both|none (default: both)
    """
    from copilot_core.floorplan.manager import get_floorplan_manager
    
    export_format = request.args.get("format", "png")
    overlay = request.args.get("overlay", "both")
    
    try:
        manager = get_floorplan_manager()
        result = manager.export_floorplan(floorplan_id=floorplan_id, export_format=export_format, overlay=overlay)
        success = result.get("success", False)
        export_url = result.get("export_url")
    except Exception as e:
        _LOGGER.warning("Failed to export floorplan: %s", e)
        success = False
        export_url = None
    
    return jsonify({
        "ok": success,
        "floorplan_id": floorplan_id,
        "format": export_format,
        "overlay": overlay,
        "export_url": export_url
    })
