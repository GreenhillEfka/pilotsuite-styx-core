"""Wecker (Smart Alarm) REST API.

Endpoints under /api/v1/wecker/:
- GET    /              List all alarms
- POST   /              Create alarm
- GET    /<id>          Get alarm details
- PUT    /<id>          Update alarm
- DELETE /<id>          Delete alarm
- POST   /<id>/snooze   Snooze ringing alarm
- POST   /<id>/dismiss  Dismiss alarm
- GET    /status        Service status
- POST   /check         Manually trigger alarm check
"""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("wecker", __name__, url_prefix="/api/v1/wecker")

# Service instance (set by register_blueprints in core_setup.py)
_wecker_service = None


def init_wecker_bp(wecker_service) -> None:
    """Initialize blueprint with WeckerService instance."""
    global _wecker_service
    _wecker_service = wecker_service


def _svc():
    if not _wecker_service:
        return None
    return _wecker_service


@bp.get("/")
@require_token
def list_alarms():
    """List all alarms."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    person_id = request.args.get("person_id")
    return jsonify({"alarms": svc.list_alarms(person_id=person_id)})


@bp.post("/")
@require_token
def create_alarm():
    """Create a new alarm."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    data = request.get_json() or {}
    if not data.get("time_hhmm"):
        return jsonify({"error": "time_hhmm is required"}), 400
    if not data.get("person_id"):
        return jsonify({"error": "person_id is required"}), 400
    alarm = svc.create_alarm(data)
    return jsonify({"alarm": alarm}), 201


@bp.get("/<alarm_id>")
@require_token
def get_alarm(alarm_id: str):
    """Get alarm details."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    alarm = svc.get_alarm(alarm_id)
    if not alarm:
        return jsonify({"error": "Alarm not found"}), 404
    return jsonify({"alarm": alarm})


@bp.put("/<alarm_id>")
@require_token
def update_alarm(alarm_id: str):
    """Update alarm."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    data = request.get_json() or {}
    alarm = svc.update_alarm(alarm_id, data)
    if not alarm:
        return jsonify({"error": "Alarm not found"}), 404
    return jsonify({"alarm": alarm})


@bp.delete("/<alarm_id>")
@require_token
def delete_alarm(alarm_id: str):
    """Delete alarm."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    if not svc.delete_alarm(alarm_id):
        return jsonify({"error": "Alarm not found"}), 404
    return jsonify({"status": "deleted"})


@bp.post("/<alarm_id>/snooze")
@require_token
def snooze_alarm(alarm_id: str):
    """Snooze a ringing alarm."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    result = svc.snooze(alarm_id)
    if not result:
        return jsonify({"error": "Alarm not ringing or not found"}), 404
    return jsonify({"alarm": result})


@bp.post("/<alarm_id>/dismiss")
@require_token
def dismiss_alarm(alarm_id: str):
    """Dismiss a ringing alarm."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    result = svc.dismiss(alarm_id)
    if not result:
        return jsonify({"error": "Alarm not found"}), 404
    return jsonify({"alarm": result})


@bp.get("/status")
@require_token
def status():
    """Get wecker service status."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    return jsonify(svc.status())


@bp.post("/check")
@require_token
def check_alarms():
    """Manually trigger alarm check (normally done by scheduler)."""
    svc = _svc()
    if not svc:
        return jsonify({"error": "Wecker service not available"}), 503
    triggered = svc.check_alarms()
    return jsonify({"triggered": triggered, "count": len(triggered)})
