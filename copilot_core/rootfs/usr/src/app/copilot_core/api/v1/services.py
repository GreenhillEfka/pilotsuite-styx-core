

# ── SLICE 172: Services API Expansion ─────────────────────────────────
from flask import Blueprint

bp = Blueprint("services", __name__, url_prefix="/services")


@bp.get("/registry")
def services_registry():
    """Get full service registry with metadata.
    
    Query params:
    - domain: Filter by domain (optional)
    - limit: Max services (default 100)
    """
    from copilot_core.services.manager import get_services_manager
    
    domain = request.args.get("domain")
    
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    
    limit = max(1, min(limit, 500))
    
    try:
        manager = get_services_manager()
        registry = manager.get_registry(domain=domain, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to get services registry: %s", e)
        registry = []
    
    return jsonify({
        "ok": True,
        "services": registry,
        "count": len(registry),
        "domain": domain,
        "limit": limit,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.post("/<service_id>/test")
def services_test(service_id):
    """Test a service call without execution.
    
    Validates parameters and returns expected behavior.
    
    Body:
    - data: Service data to test
    - target: Optional target entities
    """
    data = request.get_json() or {}
    service_data = data.get("data", {})
    target = data.get("target")
    
    from copilot_core.services.manager import get_services_manager
    
    try:
        manager = get_services_manager()
        result = manager.test_service(service_id=service_id, data=service_data, target=target)
        valid = result.get("valid", False)
        expected_behavior = result.get("expected_behavior", {})
        validation_errors = result.get("validation_errors", [])
    except Exception as e:
        _LOGGER.warning("Failed to test service: %s", e)
        valid = False
        expected_behavior = {}
        validation_errors = [str(e)]
    
    return jsonify({
        "ok": valid,
        "service_id": service_id,
        "valid": valid,
        "expected_behavior": expected_behavior,
        "validation_errors": validation_errors
    })


@bp.get("/history")
def services_history():
    """Get service call history.
    
    Query params:
    - service_id: Filter by service (optional)
    - limit: Max entries (default 50)
    - hours: Time range (default 24)
    """
    from copilot_core.services.manager import get_services_manager
    
    service_id = request.args.get("service_id")
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    limit = max(1, min(limit, 200))
    hours = max(1, min(hours, 720))
    
    try:
        manager = get_services_manager()
        history = manager.get_history(service_id=service_id, limit=limit, hours=hours)
    except Exception as e:
        _LOGGER.warning("Failed to get services history: %s", e)
        history = []
    
    return jsonify({
        "ok": True,
        "history": history,
        "count": len(history),
        "service_id": service_id,
        "limit": limit,
        "hours": hours
    })


@bp.get("/analytics")
def services_analytics():
    """Get service usage analytics.
    
    Query params:
    - days: Days to analyze (default 30)
    """
    from copilot_core.services.manager import get_services_manager
    
    try:
        days = int(request.args.get("days", "30"))
    except (ValueError, TypeError):
        days = 30
    
    days = max(1, min(days, 365))
    
    try:
        manager = get_services_manager()
        analytics = manager.get_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get services analytics: %s", e)
        analytics = {
            "total_calls": 0,
            "unique_services": 0,
            "most_called_services": [],
            "avg_calls_per_day": 0.0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/domains")
def services_domains():
    """List all service domains.
    
    Returns domain names with service counts.
    """
    from copilot_core.services.manager import get_services_manager
    
    try:
        manager = get_services_manager()
        domains = manager.list_domains()
    except Exception as e:
        _LOGGER.warning("Failed to list service domains: %s", e)
        domains = []
    
    return jsonify({
        "ok": True,
        "domains": domains,
        "count": len(domains),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
