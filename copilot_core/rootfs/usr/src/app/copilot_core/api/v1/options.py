

# ── SLICE 169: Options API Expansion ─────────────────────────────────

bp = Blueprint("options", __name__, url_prefix="/options")


@bp.get("/groups")
def options_groups():
    """List option groups/categories.
    
    Returns organized groups for options browsing.
    """
    from copilot_core.options.manager import get_options_manager
    
    try:
        manager = get_options_manager()
        groups = manager.list_groups()
    except Exception as e:
        _LOGGER.warning("Failed to list options groups: %s", e)
        groups = []
    
    return jsonify({
        "ok": True,
        "groups": groups,
        "count": len(groups),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/group/<group_name>")
def options_get_group(group_name):
    """Get all options in a specific group.
    
    Query params:
    - include_metadata: true|false (default: true)
    """
    from copilot_core.options.manager import get_options_manager
    
    include_metadata = request.args.get("include_metadata", "true").lower() == "true"
    
    try:
        manager = get_options_manager()
        options = manager.get_group(group_name=group_name, include_metadata=include_metadata)
    except Exception as e:
        _LOGGER.warning("Failed to get options group: %s", e)
        options = []
    
    return jsonify({
        "ok": True,
        "group": group_name,
        "options": options,
        "count": len(options),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/validate")
def options_validate():
    """Validate option values before saving.
    
    Body:
    - options: Dict of option key-value pairs to validate
    
    Returns validation errors for invalid values.
    """
    data = request.get_json() or {}
    options = data.get("options", {})
    
    if not options:
        return jsonify({
            "ok": False,
            "error": "Missing options"
        }), 400
    
    from copilot_core.options.manager import get_options_manager
    
    try:
        manager = get_options_manager()
        result = manager.validate(options=options)
        valid = result.get("valid", False)
        errors = result.get("errors", {})
    except Exception as e:
        _LOGGER.warning("Failed to validate options: %s", e)
        valid = False
        errors = {"_error": str(e)}
    
    return jsonify({
        "ok": True,
        "valid": valid,
        "errors": errors
    })


@bp.get("/history")
def options_history():
    """Get option change history.
    
    Query params:
    - key: Specific option key (optional, all if omitted)
    - limit: Max entries (default 50)
    - days: Days to look back (default 30)
    """
    from copilot_core.options.manager import get_options_manager
    
    key = request.args.get("key")
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    limit = max(1, min(limit, 200))
    days = max(1, min(days, 365))
    
    try:
        manager = get_options_manager()
        history = manager.get_history(key=key, limit=limit, days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get options history: %s", e)
        history = []
    
    return jsonify({
        "ok": True,
        "history": history,
        "count": len(history),
        "key": key,
        "limit": limit,
        "days": days
    })


@bp.post("/<key>/reset")
def options_reset(key):
    """Reset an option to its default value.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("RESET_OPTION", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.options.manager import get_options_manager
    
    try:
        manager = get_options_manager()
        result = manager.reset(key=key)
        success = result.get("success", False)
        default_value = result.get("default_value")
    except Exception as e:
        _LOGGER.warning("Failed to reset option: %s", e)
        success = False
        default_value = None
    
    return jsonify({
        "ok": success,
        "key": key,
        "default_value": default_value
    })


@bp.post("/reset-all")
def options_reset_all():
    """Reset all options to defaults.
    
    Requires admin token.
    
    Body:
    - group: Optional group to reset (all if omitted)
    """
    auth_error = _require_admin_mutation("RESET_ALL_OPTIONS", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    group = data.get("group")
    
    from copilot_core.options.manager import get_options_manager
    
    try:
        manager = get_options_manager()
        result = manager.reset_all(group=group)
        success = result.get("success", False)
        reset_count = result.get("reset_count", 0)
    except Exception as e:
        _LOGGER.warning("Failed to reset all options: %s", e)
        success = False
        reset_count = 0
    
    return jsonify({
        "ok": success,
        "group": group,
        "reset_count": reset_count
    })


@bp.get("/defaults")
def options_defaults():
    """Get all default option values.
    
    Query params:
    - group: Optional group filter
    """
    from copilot_core.options.manager import get_options_manager
    
    group = request.args.get("group")
    
    try:
        manager = get_options_manager()
        defaults = manager.get_defaults(group=group)
    except Exception as e:
        _LOGGER.warning("Failed to get option defaults: %s", e)
        defaults = {}
    
    return jsonify({
        "ok": True,
        "defaults": defaults,
        "group": group,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
