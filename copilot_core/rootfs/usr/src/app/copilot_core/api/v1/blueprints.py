

# ── SLICE 173: Blueprints API Expansion ─────────────────────────────────

@bp.get("/categories")
def blueprints_categories():
    """List blueprint categories.
    
    Returns organized categories for blueprint browsing.
    """
    from copilot_core.blueprints.manager import get_blueprints_manager
    
    try:
        manager = get_blueprints_manager()
        categories = manager.list_categories()
    except Exception as e:
        _LOGGER.warning("Failed to list blueprint categories: %s", e)
        categories = []
    
    return jsonify({
        "ok": True,
        "categories": categories,
        "count": len(categories),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/validate")
def blueprints_validate():
    """Validate a blueprint YAML before import.
    
    Body:
    - yaml: Blueprint YAML content to validate
    """
    data = request.get_json() or {}
    yaml_content = data.get("yaml")
    
    if not yaml_content:
        return jsonify({
            "ok": False,
            "error": "Missing yaml content"
        }), 400
    
    from copilot_core.blueprints.manager import get_blueprints_manager
    
    try:
        manager = get_blueprints_manager()
        result = manager.validate(yaml_content=yaml_content)
        valid = result.get("valid", False)
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])
    except Exception as e:
        _LOGGER.warning("Failed to validate blueprint: %s", e)
        valid = False
        errors = [str(e)]
        warnings = []
    
    return jsonify({
        "ok": True,
        "valid": valid,
        "errors": errors,
        "warnings": warnings
    })


@bp.post("/import")
def blueprints_import():
    """Import a blueprint from YAML.
    
    Requires admin token.
    
    Body:
    - yaml: Blueprint YAML content
    - category: Optional category assignment
    """
    auth_error = _require_admin_mutation("IMPORT_BLUEPRINT", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    yaml_content = data.get("yaml")
    category = data.get("category")
    
    if not yaml_content:
        return jsonify({
            "ok": False,
            "error": "Missing yaml content"
        }), 400
    
    from copilot_core.blueprints.manager import get_blueprints_manager
    
    try:
        manager = get_blueprints_manager()
        result = manager.import_blueprint(yaml_content=yaml_content, category=category)
        success = result.get("success", False)
        blueprint_id = result.get("blueprint_id")
    except Exception as e:
        _LOGGER.warning("Failed to import blueprint: %s", e)
        success = False
        blueprint_id = None
    
    return jsonify({
        "ok": success,
        "blueprint_id": blueprint_id,
        "category": category
    })


@bp.get("/<blueprint_id>/export")
def blueprints_export(blueprint_id):
    """Export a blueprint as YAML.
    
    Query params:
    - format: yaml|json (default: yaml)
    """
    from copilot_core.blueprints.manager import get_blueprints_manager
    
    export_format = request.args.get("format", "yaml")
    
    try:
        manager = get_blueprints_manager()
        result = manager.export_blueprint(blueprint_id=blueprint_id, export_format=export_format)
        success = result.get("success", False)
        content = result.get("content", "")
    except Exception as e:
        _LOGGER.warning("Failed to export blueprint: %s", e)
        success = False
        content = ""
    
    return jsonify({
        "ok": success,
        "blueprint_id": blueprint_id,
        "format": export_format,
        "content": content
    })


@bp.get("/analytics")
def blueprints_analytics():
    """Get blueprint usage analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.blueprints.manager import get_blueprints_manager
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        manager = get_blueprints_manager()
        analytics = manager.get_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get blueprint analytics: %s", e)
        analytics = {
            "total_blueprints": 0,
            "total_imports": 0,
            "most_popular": [],
            "avg_imports_per_day": 0.0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/community")
def blueprints_community():
    """List community blueprints (available for download).
    
    Query params:
    - category: Filter by category (optional)
    - limit: Max results (default 20)
    """
    from copilot_core.blueprints.manager import get_blueprints_manager
    
    category = request.args.get("category")
    
    try:
        limit = int(request.args.get("limit", "20"))
    except (ValueError, TypeError):
        limit = 20
    
    limit = max(1, min(limit, 100))
    
    try:
        manager = get_blueprints_manager()
        community = manager.list_community(category=category, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to list community blueprints: %s", e)
        community = []
    
    return jsonify({
        "ok": True,
        "community": community,
        "count": len(community),
        "category": category,
        "limit": limit
    })
