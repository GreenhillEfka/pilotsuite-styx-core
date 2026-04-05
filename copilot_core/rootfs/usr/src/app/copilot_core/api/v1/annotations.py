

# ── SLICE 161: Annotations API Expansion ─────────────────────────────────

@bp.get("/layers")
def annotations_layers():
    """List annotation layers.
    
    Returns organized layers for grouping annotations.
    """
    from copilot_core.annotations.manager import get_annotations_manager
    
    try:
        manager = get_annotations_manager()
        layers = manager.list_layers()
    except Exception as e:
        _LOGGER.warning("Failed to list annotation layers: %s", e)
        layers = []
    
    return jsonify({
        "ok": True,
        "layers": layers,
        "count": len(layers),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/layers")
def annotations_create_layer():
    """Create a new annotation layer.
    
    Body:
    - name: Layer name
    - description: Optional description
    - color: Optional color code
    """
    data = request.get_json() or {}
    name = data.get("name")
    description = data.get("description", "")
    color = data.get("color")
    
    if not name:
        return jsonify({
            "ok": False,
            "error": "Missing name"
        }), 400
    
    from copilot_core.annotations.manager import get_annotations_manager
    
    try:
        manager = get_annotations_manager()
        layer_id = manager.create_layer(name=name, description=description, color=color)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to create annotation layer: %s", e)
        success = False
        layer_id = None
    
    return jsonify({
        "ok": success,
        "layer_id": layer_id,
        "name": name,
        "description": description
    })


@bp.get("/query")
def annotations_query():
    """Query annotations with filters.
    
    Query params:
    - type: Annotation type filter (optional)
    - zone_id: Zone filter (optional)
    - layer_id: Layer filter (optional)
    - from_date: Start date (optional, ISO format)
    - to_date: End date (optional, ISO format)
    - limit: Max results (default 50)
    """
    from copilot_core.annotations.manager import get_annotations_manager
    
    ann_type = request.args.get("type")
    zone_id = request.args.get("zone_id")
    layer_id = request.args.get("layer_id")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    limit = max(1, min(limit, 200))
    
    try:
        manager = get_annotations_manager()
        annotations = manager.query(
            ann_type=ann_type,
            zone_id=zone_id,
            layer_id=layer_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit
        )
    except Exception as e:
        _LOGGER.warning("Failed to query annotations: %s", e)
        annotations = []
    
    return jsonify({
        "ok": True,
        "annotations": annotations,
        "count": len(annotations),
        "filters": {
            "type": ann_type,
            "zone_id": zone_id,
            "layer_id": layer_id,
            "from_date": from_date,
            "to_date": to_date
        },
        "limit": limit
    })


@bp.get("/export")
def annotations_export():
    """Export annotations to external format.
    
    Query params:
    - format: json|csv|geojson (default: json)
    - layer_id: Optional layer filter
    """
    from copilot_core.annotations.manager import get_annotations_manager
    
    export_format = request.args.get("format", "json")
    layer_id = request.args.get("layer_id")
    
    try:
        manager = get_annotations_manager()
        export_data = manager.export_data(export_format=export_format, layer_id=layer_id)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to export annotations: %s", e)
        export_data = None
        success = False
    
    if not success or not export_data:
        return jsonify({
            "ok": False,
            "error": "Export failed"
        }), 400
    
    return jsonify({
        "ok": True,
        "format": export_format,
        "layer_id": layer_id,
        "data": export_data
    })
