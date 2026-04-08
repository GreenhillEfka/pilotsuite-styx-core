"""User Hints API Blueprint."""

from flask import Blueprint, request, jsonify
from typing import Dict, Any

from .service import UserHintsService
from .models import HintStatus, HintType

bp = Blueprint('user_hints', __name__, url_prefix='/hints')

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401

# Global service instance
_hints_service: UserHintsService = None


def init_hints_service(service: UserHintsService) -> None:
    """Initialize the hints service."""
    global _hints_service
    _hints_service = service


def get_hints_service() -> UserHintsService:
    """Get the hints service, auto-wiring AutomationCreator if available."""
    global _hints_service
    if _hints_service is None:
        # Try to get AutomationCreator from Flask app context
        automation_creator = None
        try:
            from flask import current_app
            services = current_app.config.get("COPILOT_SERVICES", {})
            automation_creator = services.get("automation_creator")
        except Exception:
            pass
        _hints_service = UserHintsService(automation_creator=automation_creator)
    return _hints_service


@bp.route('', methods=['GET'])
def list_hints():
    """List all hints."""
    service = get_hints_service()
    status_filter = request.args.get('status')
    
    status = None
    if status_filter:
        try:
            status = HintStatus(status_filter)
        except ValueError:
            return jsonify({"error": f"Invalid status: {status_filter}"}), 400
    
    hints = service.get_hints(status=status)
    return jsonify({
        "ok": True,
        "hints": [h.to_dict() for h in hints],
        "count": len(hints),
    })


@bp.route('', methods=['POST'])
def add_hint():
    """Add a new user hint."""
    service = get_hints_service()
    
    data = request.get_json(silent=True) or {}
    text = data.get('text', '')
    hint_type_str = data.get('type')
    
    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400
    
    hint_type = None
    if hint_type_str:
        try:
            hint_type = HintType(hint_type_str)
        except ValueError:
            return jsonify({"error": f"Invalid type: {hint_type_str}"}), 400
    
    # Run async in sync context
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    hint = loop.run_until_complete(service.add_hint(text, hint_type))
    
    return jsonify({
        "ok": True,
        "hint": hint.to_dict(),
    }), 201


@bp.route('/<hint_id>', methods=['GET'])
def get_hint(hint_id: str):
    """Get a specific hint."""
    service = get_hints_service()
    hint = service._hints.get(hint_id)
    
    if not hint:
        return jsonify({"error": f"Hint not found: {hint_id}"}), 404
    
    return jsonify({
        "ok": True,
        "hint": hint.to_dict(),
    })


@bp.route('/<hint_id>/accept', methods=['POST'])
def accept_hint(hint_id: str):
    """Accept a hint suggestion and create the automation."""
    service = get_hints_service()
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    success = loop.run_until_complete(service.accept_suggestion(hint_id))
    
    if not success:
        return jsonify({"error": "Failed to accept suggestion"}), 400
    
    return jsonify({
        "ok": True,
        "message": "Suggestion accepted and automation created",
        "hint_id": hint_id,
    })


@bp.route('/<hint_id>/reject', methods=['POST'])
def reject_hint(hint_id: str):
    """Reject a hint suggestion."""
    service = get_hints_service()
    
    data = request.get_json(silent=True) or {}
    reason = data.get('reason')
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    success = loop.run_until_complete(service.reject_suggestion(hint_id, reason))
    
    if not success:
        return jsonify({"error": "Failed to reject suggestion"}), 400
    
    return jsonify({
        "ok": True,
        "message": "Suggestion rejected",
        "hint_id": hint_id,
    })


@bp.route('/suggestions', methods=['GET'])
def list_suggestions():
    """List all suggestions."""
    service = get_hints_service()
    suggestions = service.get_suggestions()
    
    return jsonify({
        "ok": True,
        "suggestions": [s.to_automation() for s in suggestions],
        "count": len(suggestions),
    })


@bp.route('/types', methods=['GET'])
def list_hint_types():
    """List available hint types."""
    return jsonify({
        "ok": True,
        "types": [
            {"value": t.value, "name": t.name}
            for t in HintType
        ],
    })