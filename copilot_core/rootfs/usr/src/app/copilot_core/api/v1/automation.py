

# ── SLICE 155: Automation API Expansion ─────────────────────────────────

bp = Blueprint("automation", __name__, url_prefix="/automation")


@bp.get("/templates")
def automation_templates():
    """List available automation templates.
    
    Returns pre-built automation templates for common use cases.
    """
    from copilot_core.automation.engine import get_automation_engine
    
    try:
        engine = get_automation_engine()
        templates = engine.list_templates()
    except Exception as e:
        _LOGGER.warning("Failed to list automation templates: %s", e)
        templates = []
    
    return jsonify({
        "ok": True,
        "templates": templates,
        "count": len(templates),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/templates/<template_id>/apply")
def automation_apply_template(template_id):
    """Apply an automation template.
    
    Requires admin token.
    
    Body:
    - name: Name for the new automation
    - params: Template-specific parameters
    """
    auth_error = _require_admin_mutation("APPLY_AUTOMATION_TEMPLATE", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    name = data.get("name", f"Template: {template_id}")
    params = data.get("params", {})
    
    from copilot_core.automation.engine import get_automation_engine
    
    try:
        engine = get_automation_engine()
        result = engine.apply_template(template_id=template_id, name=name, params=params)
        success = result.get("success", False)
        rule_id = result.get("rule_id")
    except Exception as e:
        _LOGGER.warning("Failed to apply template: %s", e)
        success = False
        rule_id = None
    
    return jsonify({
        "ok": success,
        "rule_id": rule_id,
        "template_id": template_id,
        "name": name
    })


@bp.post("/test")
def automation_test():
    """Test an automation rule without deploying.
    
    Requires admin token.
    
    Body:
    - rule: Rule definition to test
    - context: Test context/event data
    """
    auth_error = _require_admin_mutation("TEST_AUTOMATION", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    rule = data.get("rule")
    context = data.get("context", {})
    
    if not rule:
        return jsonify({
            "ok": False,
            "error": "Missing rule"
        }), 400
    
    from copilot_core.automation.engine import get_automation_engine
    
    try:
        engine = get_automation_engine()
        result = engine.test_rule(rule=rule, context=context)
        success = result.get("success", False)
        actions_triggered = result.get("actions_triggered", [])
    except Exception as e:
        _LOGGER.warning("Failed to test automation: %s", e)
        success = False
        actions_triggered = []
    
    return jsonify({
        "ok": success,
        "actions_triggered": actions_triggered,
        "context": context
    })


@bp.get("/analytics")
def automation_analytics():
    """Get automation usage analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.automation.engine import get_automation_engine
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        engine = get_automation_engine()
        analytics = engine.get_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get automation analytics: %s", e)
        analytics = {
            "total_rules": 0,
            "active_rules": 0,
            "total_triggers": 0,
            "total_actions": 0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
