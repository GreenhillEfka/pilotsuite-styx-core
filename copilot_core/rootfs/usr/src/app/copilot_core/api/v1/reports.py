

# ── SLICE 152: Reports API Expansion ─────────────────────────────────

@bp.get("/schedules")
def reports_schedules():
    """List report schedules.
    
    Returns configured automated report schedules.
    """
    from copilot_core.reports.engine import get_reports_engine
    
    try:
        engine = get_reports_engine()
        schedules = engine.list_schedules()
    except Exception as e:
        _LOGGER.warning("Failed to list report schedules: %s", e)
        schedules = []
    
    return jsonify({
        "ok": True,
        "schedules": schedules,
        "count": len(schedules),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/schedules")
def reports_create_schedule():
    """Create a new report schedule.
    
    Requires admin token.
    
    Body:
    - name: Schedule name
    - report_type: Type of report
    - frequency: daily|weekly|monthly
    - recipients: List of email addresses
    """
    auth_error = _require_admin_mutation("CREATE_REPORT_SCHEDULE", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    name = data.get("name", "Auto Report")
    report_type = data.get("report_type", "summary")
    frequency = data.get("frequency", "weekly")
    recipients = data.get("recipients", [])
    
    from copilot_core.reports.engine import get_reports_engine
    
    try:
        engine = get_reports_engine()
        schedule_id = engine.create_schedule(
            name=name,
            report_type=report_type,
            frequency=frequency,
            recipients=recipients
        )
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to create report schedule: %s", e)
        success = False
        schedule_id = None
    
    return jsonify({
        "ok": success,
        "schedule_id": schedule_id,
        "name": name,
        "report_type": report_type,
        "frequency": frequency,
        "recipients": recipients
    })


@bp.get("/<report_id>/export")
def reports_export(report_id):
    """Export report in different formats.
    
    Query params:
    - format: pdf|csv|json|html (default: json)
    """
    from copilot_core.reports.engine import get_reports_engine
    
    export_format = request.args.get("format", "json")
    
    try:
        engine = get_reports_engine()
        export_data = engine.export_report(report_id=report_id, export_format=export_format)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to export report: %s", e)
        export_data = None
        success = False
    
    if not success or not export_data:
        return jsonify({
            "ok": False,
            "error": "Export failed"
        }), 400
    
    return jsonify({
        "ok": True,
        "report_id": report_id,
        "format": export_format,
        "data": export_data
    })


@bp.get("/templates")
def reports_templates():
    """List available report templates.
    
    Returns template definitions for custom report generation.
    """
    from copilot_core.reports.engine import get_reports_engine
    
    try:
        engine = get_reports_engine()
        templates = engine.list_templates()
    except Exception as e:
        _LOGGER.warning("Failed to list templates: %s", e)
        templates = []
    
    return jsonify({
        "ok": True,
        "templates": templates,
        "count": len(templates),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
