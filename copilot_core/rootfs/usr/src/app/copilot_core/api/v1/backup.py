

# ── SLICE 151: Backup API Expansion ─────────────────────────────────

@bp.get("/schedules")
def backup_schedules():
    """List backup schedules.
    
    Returns configured automated backup schedules.
    """
    from copilot_core.backup.engine import get_backup_engine
    
    try:
        engine = get_backup_engine()
        schedules = engine.list_schedules()
    except Exception as e:
        _LOGGER.warning("Failed to list backup schedules: %s", e)
        schedules = []
    
    return jsonify({
        "ok": True,
        "schedules": schedules,
        "count": len(schedules),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/schedules")
def backup_create_schedule():
    """Create a new backup schedule.
    
    Requires admin token.
    
    Body:
    - name: Schedule name
    - frequency: daily|weekly|monthly
    - time: HH:MM for execution time
    - retention_days: Days to keep backups
    """
    auth_error = _require_admin_mutation("CREATE_BACKUP_SCHEDULE", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    name = data.get("name", "Auto Backup")
    frequency = data.get("frequency", "daily")
    time = data.get("time", "02:00")
    
    try:
        retention_days = int(data.get("retention_days", "30"))
    except (ValueError, TypeError):
        retention_days = 30
    
    from copilot_core.backup.engine import get_backup_engine
    
    try:
        engine = get_backup_engine()
        schedule_id = engine.create_schedule(
            name=name,
            frequency=frequency,
            time=time,
            retention_days=retention_days
        )
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to create backup schedule: %s", e)
        success = False
        schedule_id = None
    
    return jsonify({
        "ok": success,
        "schedule_id": schedule_id,
        "name": name,
        "frequency": frequency,
        "time": time,
        "retention_days": retention_days
    })


@bp.post("/restore")
def backup_restore():
    """Restore from a backup.
    
    Requires admin token.
    
    Body:
    - backup_id: ID of backup to restore
    - target: Restore target (default: same)
    """
    auth_error = _require_admin_mutation("RESTORE_BACKUP", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    backup_id = data.get("backup_id")
    target = data.get("target", "same")
    
    if not backup_id:
        return jsonify({
            "ok": False,
            "error": "Missing backup_id"
        }), 400
    
    from copilot_core.backup.engine import get_backup_engine
    
    try:
        engine = get_backup_engine()
        result = engine.restore(backup_id=backup_id, target=target)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to restore backup: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "backup_id": backup_id,
        "target": target
    })


@bp.get("/verify/<backup_id>")
def backup_verify(backup_id):
    """Verify backup integrity.
    
    Returns verification status and any errors found.
    """
    from copilot_core.backup.engine import get_backup_engine
    
    try:
        engine = get_backup_engine()
        result = engine.verify(backup_id=backup_id)
        valid = result.get("valid", False)
        errors = result.get("errors", [])
    except Exception as e:
        _LOGGER.warning("Failed to verify backup: %s", e)
        valid = False
        errors = [str(e)]
    
    return jsonify({
        "ok": True,
        "backup_id": backup_id,
        "valid": valid,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
