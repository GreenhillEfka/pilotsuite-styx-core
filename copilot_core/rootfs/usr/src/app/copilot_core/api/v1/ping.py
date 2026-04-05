

# ── SLICE 171: Ping API Expansion ─────────────────────────────────

bp = Blueprint("ping", __name__, url_prefix="/ping")


@bp.get("/diagnostics")
def ping_diagnostics():
    """Extended ping with component health checks.
    
    Returns ping status plus health of key components.
    """
    from copilot_core.ping.monitor import get_ping_monitor
    
    try:
        monitor = get_ping_monitor()
        result = monitor.diagnostics()
    except Exception as e:
        _LOGGER.warning("Failed to get ping diagnostics: %s", e)
        result = {
            "status": "degraded",
            "components": {},
            "errors": [str(e)]
        }
    
    return jsonify({
        "ok": result.get("status") == "healthy",
        "diagnostics": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/latency")
def ping_latency():
    """Get ping latency metrics.
    
    Query params:
    - samples: Number of samples (default 10)
    """
    from copilot_core.ping.monitor import get_ping_monitor
    
    try:
        samples = int(request.args.get("samples", "10"))
    except (ValueError, TypeError):
        samples = 10
    
    samples = max(1, min(samples, 100))
    
    try:
        monitor = get_ping_monitor()
        latency = monitor.get_latency(samples=samples)
    except Exception as e:
        _LOGGER.warning("Failed to get ping latency: %s", e)
        latency = {
            "avg_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "p95_ms": 0.0,
            "samples": []
        }
    
    return jsonify({
        "ok": True,
        "latency": latency,
        "samples": samples,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/history")
def ping_history():
    """Get historical ping data.
    
    Query params:
    - hours: Time range (default 24)
    - interval: Data point interval in minutes (default 60)
    """
    from copilot_core.ping.monitor import get_ping_monitor
    
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
        monitor = get_ping_monitor()
        history = monitor.get_history(hours=hours, interval=interval)
    except Exception as e:
        _LOGGER.warning("Failed to get ping history: %s", e)
        history = []
    
    return jsonify({
        "ok": True,
        "history": history,
        "count": len(history),
        "hours": hours,
        "interval_minutes": interval,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/alerts")
def ping_alerts():
    """Get ping-related alerts.
    
    Query params:
    - active_only: true|false (default: true)
    """
    from copilot_core.ping.monitor import get_ping_monitor
    
    active_only = request.args.get("active_only", "true").lower() == "true"
    
    try:
        monitor = get_ping_monitor()
        alerts = monitor.get_alerts(active_only=active_only)
    except Exception as e:
        _LOGGER.warning("Failed to get ping alerts: %s", e)
        alerts = []
    
    return jsonify({
        "ok": True,
        "alerts": alerts,
        "count": len(alerts),
        "active_only": active_only,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
