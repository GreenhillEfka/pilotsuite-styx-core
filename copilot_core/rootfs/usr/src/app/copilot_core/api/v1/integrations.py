

# ── SLICE 154: Integrations API Expansion ─────────────────────────────────

@bp.get("/status")
def integrations_status():
    """Get status of all integrations.
    
    Returns per-integration:
    - integration_id
    - status: active|inactive|error
    - last_sync: Last successful sync
    - error_count: Recent errors
    """
    from copilot_core.integrations.manager import get_integrations_manager
    
    try:
        manager = get_integrations_manager()
        status_list = manager.get_all_status()
    except Exception as e:
        _LOGGER.warning("Failed to get integrations status: %s", e)
        status_list = []
    
    return jsonify({
        "ok": True,
        "integrations": status_list,
        "count": len(status_list),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/<integration_id>/status")
def integration_status(integration_id):
    """Get status of a specific integration.
    
    Returns detailed status info for the integration.
    """
    from copilot_core.integrations.manager import get_integrations_manager
    
    try:
        manager = get_integrations_manager()
        status = manager.get_integration_status(integration_id=integration_id)
    except Exception as e:
        _LOGGER.warning("Failed to get integration status: %s", e)
        status = {
            "integration_id": integration_id,
            "status": "unknown",
            "last_sync": None,
            "error_count": 0
        }
    
    return jsonify({
        "ok": True,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/<integration_id>/sync")
def integration_sync(integration_id):
    """Trigger manual sync for an integration.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("SYNC_INTEGRATION", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.integrations.manager import get_integrations_manager
    
    try:
        manager = get_integrations_manager()
        result = manager.trigger_sync(integration_id=integration_id)
        success = result.get("success", False)
        synced_items = result.get("synced_items", 0)
    except Exception as e:
        _LOGGER.warning("Failed to sync integration: %s", e)
        success = False
        synced_items = 0
    
    return jsonify({
        "ok": success,
        "integration_id": integration_id,
        "synced_items": synced_items
    })


@bp.get("/<integration_id>/logs")
def integration_logs(integration_id):
    """Get activity logs for an integration.
    
    Query params:
    - limit: Max entries (default 50)
    - level: INFO|WARNING|ERROR (optional)
    """
    from copilot_core.integrations.manager import get_integrations_manager
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    level = request.args.get("level")
    
    limit = max(1, min(limit, 200))
    
    try:
        manager = get_integrations_manager()
        logs = manager.get_logs(integration_id=integration_id, limit=limit, level=level)
    except Exception as e:
        _LOGGER.warning("Failed to get integration logs: %s", e)
        logs = []
    
    return jsonify({
        "ok": True,
        "logs": logs,
        "count": len(logs),
        "integration_id": integration_id,
        "limit": limit,
        "level": level
    })
