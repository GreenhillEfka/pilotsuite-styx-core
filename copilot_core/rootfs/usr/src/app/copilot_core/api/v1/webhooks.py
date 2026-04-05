

# ── SLICE 153: Webhooks API Expansion ─────────────────────────────────

@bp.get("/triggers")
def webhooks_triggers():
    """List available webhook triggers.
    
    Returns all trigger types that can be used for webhook subscriptions.
    """
    from copilot_core.webhooks.engine import get_webhooks_engine
    
    try:
        engine = get_webhooks_engine()
        triggers = engine.list_triggers()
    except Exception as e:
        _LOGGER.warning("Failed to list webhook triggers: %s", e)
        triggers = []
    
    return jsonify({
        "ok": True,
        "triggers": triggers,
        "count": len(triggers),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/<webhook_id>/logs")
def webhooks_logs(webhook_id):
    """Get delivery logs for a webhook.
    
    Query params:
    - limit: Max entries (default 50)
    - status: success|failed|pending (optional)
    """
    from copilot_core.webhooks.engine import get_webhooks_engine
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    status = request.args.get("status")
    
    limit = max(1, min(limit, 200))
    
    try:
        engine = get_webhooks_engine()
        logs = engine.get_logs(webhook_id=webhook_id, limit=limit, status=status)
    except Exception as e:
        _LOGGER.warning("Failed to get webhook logs: %s", e)
        logs = []
    
    return jsonify({
        "ok": True,
        "logs": logs,
        "count": len(logs),
        "webhook_id": webhook_id,
        "limit": limit,
        "status": status
    })


@bp.post("/<webhook_id>/retry")
def webhooks_retry(webhook_id):
    """Retry failed deliveries for a webhook.
    
    Requires admin token.
    
    Body:
    - log_ids: Optional list of specific log IDs to retry
    """
    auth_error = _require_admin_mutation("RETRY_WEBHOOK", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    log_ids = data.get("log_ids")
    
    from copilot_core.webhooks.engine import get_webhooks_engine
    
    try:
        engine = get_webhooks_engine()
        result = engine.retry_deliveries(webhook_id=webhook_id, log_ids=log_ids)
        success = result.get("success", False)
        retried = result.get("retried", 0)
    except Exception as e:
        _LOGGER.warning("Failed to retry webhook deliveries: %s", e)
        success = False
        retried = 0
    
    return jsonify({
        "ok": success,
        "webhook_id": webhook_id,
        "retried": retried
    })


@bp.post("/test")
def webhooks_test():
    """Test webhook delivery.
    
    Requires admin token.
    
    Body:
    - url: Target URL
    - event: Test event payload
    """
    auth_error = _require_admin_mutation("TEST_WEBHOOK", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    url = data.get("url")
    event = data.get("event", {"test": True})
    
    if not url:
        return jsonify({
            "ok": False,
            "error": "Missing url"
        }), 400
    
    from copilot_core.webhooks.engine import get_webhooks_engine
    
    try:
        engine = get_webhooks_engine()
        result = engine.test_delivery(url=url, event=event)
        success = result.get("success", False)
        response_code = result.get("response_code")
    except Exception as e:
        _LOGGER.warning("Failed to test webhook: %s", e)
        success = False
        response_code = None
    
    return jsonify({
        "ok": success,
        "url": url,
        "response_code": response_code,
        "event": event
    })
