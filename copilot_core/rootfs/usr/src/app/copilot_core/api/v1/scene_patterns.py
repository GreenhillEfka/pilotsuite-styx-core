"""Scene Pattern API - PilotSuite v7.11.0

API endpoints for scene pattern extraction and suggestions.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

scene_patterns_bp = Blueprint("scene_patterns", __name__, url_prefix="/api/v1/scenes/patterns")


def _get_pattern_extractor():
    """Get scene pattern extractor instance."""
    try:
        from copilot_core.scene_patterns import get_scene_pattern_extractor
        return get_scene_pattern_extractor()
    except Exception as e:
        logger.error(f"Failed to get pattern extractor: {e}")
        return None


@scene_patterns_bp.route("/record", methods=["POST"])
@require_token
def record_activation():
    """Record a scene activation to learn patterns."""
    extractor = _get_pattern_extractor()
    if not extractor:
        return jsonify({"error": "Pattern extractor not available"}), 503
    
    data = request.get_json() or {}
    scene_id = data.get("scene_id")
    if not scene_id:
        return jsonify({"error": "scene_id required"}), 400
    
    context = data.get("context")
    extractor.record_scene_activation(scene_id, context)
    
    return jsonify({
        "ok": True,
        "scene_id": scene_id,
        "message": "Pattern recorded",
    })


@scene_patterns_bp.route("/suggest", methods=["GET"])
@require_token
def suggest_scenes():
    """Get scene suggestions based on learned patterns."""
    extractor = _get_pattern_extractor()
    if not extractor:
        return jsonify({"error": "Pattern extractor not available"}), 503
    
    context = request.args.to_dict()
    suggestions = extractor.suggest_scenes(context)
    
    return jsonify({
        "ok": True,
        "suggestions": suggestions,
        "count": len(suggestions),
    })


@scene_patterns_bp.route("/summary", methods=["GET"])
@require_token
def get_summary():
    """Get pattern summary."""
    extractor = _get_pattern_extractor()
    if not extractor:
        return jsonify({"error": "Pattern extractor not available"}), 503
    
    summary = extractor.get_pattern_summary()
    
    return jsonify({
        "ok": True,
        "summary": summary,
    })


@scene_patterns_bp.route("/clear", methods=["POST"])
@require_token
def clear_patterns():
    """Clear all learned patterns."""
    extractor = _get_pattern_extractor()
    if not extractor:
        return jsonify({"error": "Pattern extractor not available"}), 503
    
    extractor.clear_patterns()
    
    return jsonify({
        "ok": True,
        "message": "Patterns cleared",
    })
