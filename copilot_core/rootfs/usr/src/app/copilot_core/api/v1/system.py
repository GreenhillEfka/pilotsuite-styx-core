

# ── SLICE 170: System API Expansion ─────────────────────────────────

bp = Blueprint("system", __name__, url_prefix="/system")


@bp.post("/restart")
def system_restart():
    """Trigger system restart.
    
    Requires admin token.
    
    Body:
    - delay_seconds: Delay before restart (default: 5)
    - reason: Optional restart reason
    """
    auth_error = _require_admin_mutation("SYSTEM_RESTART", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    delay = data.get("delay_seconds", 5)
    reason = data.get("reason", "User requested")
    
    from copilot_core.system.controller import get_system_controller
    
    try:
        controller = get_system_controller()
        result = controller.restart(delay_seconds=delay, reason=reason)
        success = result.get("success", False)
        scheduled_at = result.get("scheduled_at")
    except Exception as e:
        _LOGGER.warning("Failed to schedule system restart: %s", e)
        success = False
        scheduled_at = None
    
    return jsonify({
        "ok": success,
        "scheduled_at": scheduled_at,
        "delay_seconds": delay,
        "reason": reason
    })


@bp.get("/updates")
def system_updates():
    """Check for available system updates.
    
    Returns current version and available updates.
    """
    from copilot_core.system.controller import get_system_controller
    
    try:
        controller = get_system_controller()
        updates = controller.check_updates()
    except Exception as e:
        _LOGGER.warning("Failed to check updates: %s", e)
        updates = {
            "current_version": "unknown",
            "available_updates": [],
            "latest_version": None
        }
    
    return jsonify({
        "ok": True,
        "updates": updates,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/updates/apply")
def system_apply_update():
    """Apply a system update.
    
    Requires admin token.
    
    Body:
    - version: Target version (optional, latest if omitted)
    - restart: Whether to restart after update (default: true)
    """
    auth_error = _require_admin_mutation("SYSTEM_UPDATE", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    version = data.get("version")
    restart = data.get("restart", True)
    
    from copilot_core.system.controller import get_system_controller
    
    try:
        controller = get_system_controller()
        result = controller.apply_update(version=version, restart=restart)
        success = result.get("success", False)
        updated_version = result.get("updated_version")
    except Exception as e:
        _LOGGER.warning("Failed to apply update: %s", e)
        success = False
        updated_version = None
    
    return jsonify({
        "ok": success,
        "updated_version": updated_version,
        "restart": restart
    })


@bp.get("/logs")
def system_logs():
    """Get system logs.
    
    Query params:
    - lines: Number of lines (default 100)
    - level: DEBUG|INFO|WARNING|ERROR (optional)
    - source: Specific log source (optional)
    """
    from copilot_core.system.logs import get_system_logs
    
    try:
        lines = int(request.args.get("lines", "100"))
    except (ValueError, TypeError):
        lines = 100
    
    level = request.args.get("level")
    source = request.args.get("source")
    
    lines = max(1, min(lines, 1000))
    
    try:
        logs_service = get_system_logs()
        logs = logs_service.get_lines(lines=lines, level=level, source=source)
    except Exception as e:
        _LOGGER.warning("Failed to get system logs: %s", e)
        logs = []
    
    return jsonify({
        "ok": True,
        "logs": logs,
        "count": len(logs),
        "lines": lines,
        "level": level,
        "source": source
    })


@bp.get("/logs/download")
def system_logs_download():
    """Download system logs as file.
    
    Query params:
    - format: txt|json|zip (default: txt)
    - hours: Hours of logs to include (default 24)
    """
    from copilot_core.system.logs import get_system_logs
    
    download_format = request.args.get("format", "txt")
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    hours = max(1, min(hours, 720))
    
    try:
        logs_service = get_system_logs()
        result = logs_service.export(format=download_format, hours=hours)
        success = result.get("success", False)
        download_url = result.get("download_url")
    except Exception as e:
        _LOGGER.warning("Failed to export logs: %s", e)
        success = False
        download_url = None
    
    return jsonify({
        "ok": success,
        "format": download_format,
        "hours": hours,
        "download_url": download_url
    })


@bp.get("/diagnostics")
def system_diagnostics():
    """Get full system diagnostic bundle.
    
    Returns comprehensive system info for troubleshooting.
    """
    from copilot_core.system.controller import get_system_controller
    
    try:
        controller = get_system_controller()
        diagnostics = controller.get_diagnostics()
    except Exception as e:
        _LOGGER.warning("Failed to get diagnostics: %s", e)
        diagnostics = {
            "system_info": {},
            "health": {},
            "errors": [str(e)]
        }
    
    return jsonify({
        "ok": True,
        "diagnostics": diagnostics,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/resources")
def system_resources():
    """Get system resource usage.
    
    Returns CPU, memory, disk, network usage.
    """
    from copilot_core.system.controller import get_system_controller
    
    try:
        controller = get_system_controller()
        resources = controller.get_resource_usage()
    except Exception as e:
        _LOGGER.warning("Failed to get resource usage: %s", e)
        resources = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "disk_percent": 0.0,
            "network": {}
        }
    
    return jsonify({
        "ok": True,
        "resources": resources,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
