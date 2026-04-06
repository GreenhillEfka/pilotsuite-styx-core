

# ── SLICE 163: Templates API Expansion ─────────────────────────────────
from flask import Blueprint

bp = Blueprint("templates", __name__, url_prefix="/templates")


@bp.get("/categories")
def templates_categories():
    """List template categories.
    
    Returns organized categories for template browsing.
    """
    from copilot_core.templates.manager import get_templates_manager
    
    try:
        manager = get_templates_manager()
        categories = manager.list_categories()
    except Exception as e:
        _LOGGER.warning("Failed to list template categories: %s", e)
        categories = []
    
    return jsonify({
        "ok": True,
        "categories": categories,
        "count": len(categories),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/variables")
def templates_variables():
    """List available template variables.
    
    Returns variable definitions that can be used in templates.
    """
    from copilot_core.templates.manager import get_templates_manager
    
    try:
        manager = get_templates_manager()
        variables = manager.list_variables()
    except Exception as e:
        _LOGGER.warning("Failed to list template variables: %s", e)
        variables = []
    
    return jsonify({
        "ok": True,
        "variables": variables,
        "count": len(variables),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/<template_id>/preview")
def templates_preview(template_id):
    """Preview template rendering with variables.
    
    Body:
    - variables: Variable values for rendering
    """
    data = request.get_json() or {}
    variables = data.get("variables", {})
    
    from copilot_core.templates.manager import get_templates_manager
    
    try:
        manager = get_templates_manager()
        result = manager.preview(template_id=template_id, variables=variables)
        success = result.get("success", False)
        rendered = result.get("rendered", "")
    except Exception as e:
        _LOGGER.warning("Failed to preview template: %s", e)
        success = False
        rendered = ""
    
    return jsonify({
        "ok": success,
        "template_id": template_id,
        "rendered": rendered,
        "variables": variables
    })


@bp.get("/export")
def templates_export():
    """Export templates to external format.
    
    Query params:
    - format: json|yaml|zip (default: json)
    - category: Optional category filter
    """
    from copilot_core.templates.manager import get_templates_manager
    
    export_format = request.args.get("format", "json")
    category = request.args.get("category")
    
    try:
        manager = get_templates_manager()
        export_data = manager.export_data(export_format=export_format, category=category)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to export templates: %s", e)
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
        "category": category,
        "data": export_data
    })


@bp.post("/import")
def templates_import():
    """Import templates from external format.
    
    Requires admin token.
    
    Body:
    - data: Template data to import
    - format: json|yaml|zip (default: json)
    - category: Optional target category
    """
    auth_error = _require_admin_mutation("IMPORT_TEMPLATES", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    import_data = data.get("data")
    import_format = data.get("format", "json")
    category = data.get("category")
    
    if not import_data:
        return jsonify({
            "ok": False,
            "error": "Missing data"
        }), 400
    
    from copilot_core.templates.manager import get_templates_manager
    
    try:
        manager = get_templates_manager()
        result = manager.import_data(data=import_data, import_format=import_format, category=category)
        success = result.get("success", False)
        imported_count = result.get("imported_count", 0)
    except Exception as e:
        _LOGGER.warning("Failed to import templates: %s", e)
        success = False
        imported_count = 0
    
    return jsonify({
        "ok": success,
        "imported_count": imported_count,
        "format": import_format,
        "category": category
    })
