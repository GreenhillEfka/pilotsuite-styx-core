"""Health API compatibility bridge for blueprint reconciliation."""

from copilot_core.system_health.api import (

bp = Blueprint("health", __name__, url_prefix="/health")

    init_system_health_api,
    system_health_bp as health_bp,
)

__all__ = ["health_bp", "init_system_health_api"]


# ── SLICE 149: Health API Expansion ─────────────────────────────────

@bp.get("/components")
def health_components():
    """Get health status of all system components.
    
    Returns per-component:
    - component_id
    - status: healthy|degraded|unhealthy
    - last_check: Last health check timestamp
    - details: Component-specific health info
    """
    from copilot_core.health.monitor import get_health_monitor
    
    try:
        monitor = get_health_monitor()
        components = monitor.get_components_health()
    except Exception as e:
        _LOGGER.warning("Failed to get components health: %s", e)
        components = []
    
    return jsonify({
        "ok": True,
        "components": components,
        "count": len(components),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/components/<component_id>")
def health_component(component_id):
    """Get health status of a specific component.
    
    Returns detailed health info for the component.
    """
    from copilot_core.health.monitor import get_health_monitor
    
    try:
        monitor = get_health_monitor()
        health = monitor.get_component_health(component_id=component_id)
    except Exception as e:
        _LOGGER.warning("Failed to get component health: %s", e)
        health = {
            "component_id": component_id,
            "status": "unknown",
            "last_check": None,
            "details": {}
        }
    
    return jsonify({
        "ok": True,
        "health": health,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/trends")
def health_trends():
    """Get health trends over time.
    
    Query params:
    - hours: Time range (default 24)
    - interval: Data point interval in minutes (default 60)
    """
    from copilot_core.health.monitor import get_health_monitor
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    try:
        interval = int(request.args.get("interval", "60"))
    except (ValueError, TypeError):
        interval = 60
    
    hours = max(1, min(hours, 720))
    interval = max(5, min(interval, 1440))
    
    try:
        monitor = get_health_monitor()
        trends = monitor.get_health_trends(hours=hours, interval=interval)
    except Exception as e:
        _LOGGER.warning("Failed to get health trends: %s", e)
        trends = []
    
    return jsonify({
        "ok": True,
        "trends": trends,
        "hours": hours,
        "interval_minutes": interval,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/alerts")
def health_alerts():
    """Get active health alerts.
    
    Query params:
    - severity: critical|warning|info (optional, all if omitted)
    - active_only: true|false (default: true)
    """
    from copilot_core.health.monitor import get_health_monitor
    
    severity = request.args.get("severity")
    active_only = request.args.get("active_only", "true").lower() == "true"
    
    try:
        monitor = get_health_monitor()
        alerts = monitor.get_alerts(severity=severity, active_only=active_only)
    except Exception as e:
        _LOGGER.warning("Failed to get health alerts: %s", e)
        alerts = []
    
    return jsonify({
        "ok": True,
        "alerts": alerts,
        "count": len(alerts),
        "severity": severity,
        "active_only": active_only,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
