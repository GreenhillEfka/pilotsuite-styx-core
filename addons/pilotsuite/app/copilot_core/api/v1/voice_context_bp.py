"""Voice Context API Blueprint for HA Assist integration."""
from flask import Blueprint, jsonify, request

from copilot_core.api.v1.voice_context import get_voice_context_provider

bp = Blueprint("voice_context", __name__, url_prefix="/voice")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


@bp.route("/context", methods=["GET"])
def get_context():
    """Get current voice context for HA Assist.
    
    Returns:
        JSON with mood, zone, and voice suggestions.
    """
    provider = get_voice_context_provider()
    return jsonify(provider.get_context_dict())


@bp.route("/context", methods=["POST"])
def update_context():
    """Update voice context from neural system.
    
    Request body:
        {
            "mood": {"mood": "relax", "confidence": 0.8, "contributors": [...]},
            "zone": {"current_zone": "wohnzimmer", "presence": ["wohnzimmer"]},
            "suggestions": [{"action": "light.on", "confidence": 0.9}]
        }
    """
    data = request.get_json() or {}
    
    provider = get_voice_context_provider()
    context = provider.update_from_neural_state(
        mood_data=data.get("mood", {}),
        zone_data=data.get("zone"),
        suggestion_data=data.get("suggestions"),
    )
    
    return jsonify({
        "success": True,
        "context": provider.get_context_dict(),
    })


@bp.route("/prompt", methods=["GET"])
def get_prompt():
    """Get voice prompt for HA Assist templates.
    
    Returns:
        Plain text prompt describing current context.
    """
    provider = get_voice_context_provider()
    return provider.get_voice_prompt()


@bp.route("/mood_history", methods=["GET"])
def get_mood_history():
    """Get recent mood history for trend analysis.
    
    Query params:
        limit: Number of entries to return (default 10)
    """
    limit = request.args.get("limit", 10, type=int)
    provider = get_voice_context_provider()
    return jsonify({
        "history": provider.get_mood_history(limit=limit),
    })


@bp.route("/suggestions", methods=["GET"])
def get_suggestions():
    """Get voice-friendly suggestions based on current context.
    
    Returns:
        List of natural language suggestions.
    """
    provider = get_voice_context_provider()
    context = provider.get_context()
    return jsonify({
        "suggestions": context.voice_suggestions,
        "mood": context.dominant_mood,
        "zone": context.current_zone,
    })