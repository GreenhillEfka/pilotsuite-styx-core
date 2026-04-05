"""Debug mode endpoints for PilotSuite Core."""

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token as _validate_token
from copilot_core.debug import get_debug, set_debug

bp = Blueprint("debug", __name__, url_prefix="")


def _json_error(message: str, status: int):
    return jsonify({"error": message}), status


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return (
            jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}),
            401,
        )


@bp.route("/debug", methods=["GET"])
def get_debug_status():
    """Get debug mode status."""
    try:
        return jsonify({"debug_mode": get_debug()}), 200
    except Exception as exc:
        return _json_error(str(exc), 500)


@bp.route("/debug", methods=["POST"])
def set_debug_status():
    """Set debug mode status."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _json_error("JSON object required", 400)

    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        return _json_error("Invalid request. 'enabled' must be a boolean (true/false).", 400)

    try:
        set_debug(enabled)
    except Exception as exc:
        return _json_error(str(exc), 500)
    return jsonify({"enabled": enabled}), 200


# ── SLICE 150: Debug API Expansion ─────────────────────────────────

@bp.get("/logs/stream")
def debug_logs_stream():
    """Get real-time log stream.
    
    Query params:
    - lines: Initial lines (default 50)
    - follow: true|false for streaming (default: false)
    - level: DEBUG|INFO|WARNING|ERROR (optional)
    """
    from copilot_core.debug.logs import get_debug_logs
    
    try:
        lines = int(request.args.get("lines", "50"))
    except (ValueError, TypeError):
        lines = 50
    
    follow = request.args.get("follow", "false").lower() == "true"
    level = request.args.get("level")
    
    lines = max(1, min(lines, 1000))
    
    try:
        logs_service = get_debug_logs()
        logs = logs_service.get_logs(lines=lines, level=level, follow=follow)
    except Exception as e:
        _LOGGER.warning("Failed to get logs stream: %s", e)
        logs = []
    
    return jsonify({
        "ok": True,
        "logs": logs,
        "count": len(logs),
        "lines": lines,
        "level": level,
        "follow": follow
    })


@bp.get("/snapshot")
def debug_snapshot():
    """Get system state snapshot.
    
    Query params:
    - include: Comma-separated sections (logs,metrics,config,all)
    """
    from copilot_core.debug.snapshot import get_debug_snapshot
    
    include = request.args.get("include", "all").split(",")
    
    try:
        snapshot_service = get_debug_snapshot()
        snapshot = snapshot_service.capture(include=include)
    except Exception as e:
        _LOGGER.warning("Failed to capture snapshot: %s", e)
        snapshot = {}
    
    return jsonify({
        "ok": True,
        "snapshot": snapshot,
        "include": include,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/profiling")
def debug_profiling():
    """Get performance profiling data.
    
    Query params:
    - duration: Profile duration in seconds (default 10)
    - type: cpu|memory|all (default: all)
    """
    from copilot_core.debug.profiler import get_debug_profiler
    
    try:
        duration = int(request.args.get("duration", "10"))
    except (ValueError, TypeError):
        duration = 10
    
    profile_type = request.args.get("type", "all")
    
    duration = max(1, min(duration, 300))
    
    try:
        profiler = get_debug_profiler()
        profile = profiler.get_profile(duration=duration, profile_type=profile_type)
    except Exception as e:
        _LOGGER.warning("Failed to get profiling data: %s", e)
        profile = {}
    
    return jsonify({
        "ok": True,
        "profile": profile,
        "duration": duration,
        "type": profile_type
    })


@bp.post("/profiling/start")
def debug_profiling_start():
    """Start performance profiling session.
    
    Requires admin token.
    
    Body:
    - duration: Profile duration in seconds
    - type: cpu|memory|all
    """
    auth_error = _require_admin_mutation("START_PROFILING", "Admin token required")
    if auth_error:
        return auth_error
    
    data = request.get_json() or {}
    
    try:
        duration = int(data.get("duration", "10"))
    except (ValueError, TypeError):
        duration = 10
    
    profile_type = data.get("type", "all")
    
    from copilot_core.debug.profiler import get_debug_profiler
    
    try:
        profiler = get_debug_profiler()
        session_id = profiler.start_profiling(duration=duration, profile_type=profile_type)
        success = True
    except Exception as e:
        _LOGGER.warning("Failed to start profiling: %s", e)
        success = False
        session_id = None
    
    return jsonify({
        "ok": success,
        "session_id": session_id,
        "duration": duration,
        "type": profile_type
    })
