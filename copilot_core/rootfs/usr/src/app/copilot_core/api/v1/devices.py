

# ── SLICE 165: Devices API Expansion ─────────────────────────────────

bp = Blueprint("devices", __name__, url_prefix="/devices")


@bp.get("/registry")
def devices_registry():
    """Get full device registry.
    
    Query params:
    - limit: Max devices (default 100)
    - area_id: Filter by area (optional)
    """
    from copilot_core.devices.manager import get_devices_manager
    
    area_id = request.args.get("area_id")
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    limit = max(1, min(limit, 500))
    
    try:
        manager = get_devices_manager()
        devices = manager.list_registry(area_id=area_id, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to get device registry: %s", e)
        devices = []
    
    return jsonify({
        "ok": True,
        "devices": devices,
        "count": len(devices),
        "area_id": area_id,
        "limit": limit
    })


@bp.get("/<device_id>/entities")
def devices_entities(device_id):
    """List all entities for a device.
    
    Returns entity_id, platform, domain for each entity.
    """
    from copilot_core.devices.manager import get_devices_manager
    
    try:
        manager = get_devices_manager()
        entities = manager.get_entities(device_id=device_id)
    except Exception as e:
        _LOGGER.warning("Failed to get device entities: %s", e)
        entities = []
    
    return jsonify({
        "ok": True,
        "device_id": device_id,
        "entities": entities,
        "count": len(entities),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/<device_id>/diagnostics")
def devices_diagnostics(device_id):
    """Get diagnostic information for a device.
    
    Returns device info, manufacturer, model, firmware, connectivity status.
    """
    from copilot_core.devices.manager import get_devices_manager
    
    try:
        manager = get_devices_manager()
        diagnostics = manager.get_diagnostics(device_id=device_id)
    except Exception as e:
        _LOGGER.warning("Failed to get device diagnostics: %s", e)
        diagnostics = {
            "device_id": device_id,
            "info": {},
            "connectivity": "unknown",
            "last_seen": None
        }
    
    return jsonify({
        "ok": True,
        "device_id": device_id,
        "diagnostics": diagnostics,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/cleanup")
def devices_cleanup():
    """Remove orphaned devices.
    
    Requires admin token.
    
    Body:
    - dry_run: true|false (default: true)
    """
    auth_error = _require_admin_mutation("CLEANUP_DEVICES", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    dry_run = data.get("dry_run", True)
    
    from copilot_core.devices.manager import get_devices_manager
    
    try:
        manager = get_devices_manager()
        result = manager.cleanup_orphaned(dry_run=dry_run)
        success = result.get("success", False)
        orphaned = result.get("orphaned_count", 0)
        removed = result.get("removed_count", 0)
    except Exception as e:
        _LOGGER.warning("Failed to cleanup devices: %s", e)
        success = False
        orphaned = 0
        removed = 0
    
    return jsonify({
        "ok": success,
        "dry_run": dry_run,
        "orphaned": orphaned,
        "removed": removed
    })


@bp.get("/<device_id>/area")
def devices_get_area(device_id):
    """Get area assignment for a device.
    
    Returns area_id, area_name if assigned.
    """
    from copilot_core.devices.manager import get_devices_manager
    
    try:
        manager = get_devices_manager()
        area = manager.get_area(device_id=device_id)
    except Exception as e:
        _LOGGER.warning("Failed to get device area: %s", e)
        area = None
    
    return jsonify({
        "ok": True,
        "device_id": device_id,
        "area": area,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.put("/<device_id>/area")
def devices_set_area(device_id):
    """Set area assignment for a device.
    
    Requires admin token.
    
    Body:
    - area_id: Area ID to assign (null to remove)
    """
    auth_error = _require_admin_mutation("SET_DEVICE_AREA", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    area_id = data.get("area_id")
    
    from copilot_core.devices.manager import get_devices_manager
    
    try:
        manager = get_devices_manager()
        result = manager.set_area(device_id=device_id, area_id=area_id)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to set device area: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "device_id": device_id,
        "area_id": area_id
    })
