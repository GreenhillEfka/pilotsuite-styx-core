"""Routine Pattern API - PilotSuite v7.11.0

API endpoints for routine pattern extraction and predictions.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

routine_patterns_bp = Blueprint("routine_patterns", __name__, url_prefix="/api/v1/routines")


def _get_routine_extractor():
    """Get routine pattern extractor instance."""
    try:
        from copilot_core.routine_patterns import get_routine_pattern_extractor
        return get_routine_pattern_extractor()
    except Exception as e:
        logger.error(f"Failed to get routine extractor: {e}")
        return None


@routine_patterns_bp.route("/record", methods=["POST"])
@require_token
def record_action():
    """Record a user action to learn routines."""
    extractor = _get_routine_extractor()
    if not extractor:
        return jsonify({"error": "Routine extractor not available"}), 503
    
    data = request.get_json() or {}
    action_type = data.get("action_type")
    entity_id = data.get("entity_id")
    
    if not action_type or not entity_id:
        return jsonify({"error": "action_type and entity_id required"}), 400
    
    state = data.get("state")
    context = data.get("context")
    extractor.record_action(action_type, entity_id, state, context)
    
    return jsonify({
        "ok": True,
        "message": "Action recorded",
    })


@routine_patterns_bp.route("/predict", methods=["GET"])
@require_token
def predict_next():
    """Get predicted next actions based on current time."""
    extractor = _get_routine_extractor()
    if not extractor:
        return jsonify({"error": "Routine extractor not available"}), 503
    
    predictions = extractor.predict_next_action()
    
    return jsonify({
        "ok": True,
        "predictions": predictions,
        "count": len(predictions),
    })


@routine_patterns_bp.route("/typical", methods=["GET"])
@require_token
def get_typical_routine():
    """Get typical daily routine."""
    extractor = _get_routine_extractor()
    if not extractor:
        return jsonify({"error": "Routine extractor not available"}), 503
    
    weekday_type = request.args.get("weekday_type", "weekday")
    routine = extractor.get_typical_routine(weekday_type)
    
    return jsonify({
        "ok": True,
        "weekday_type": weekday_type,
        "routine": routine,
    })


@routine_patterns_bp.route("/summary", methods=["GET"])
@require_token
def get_summary():
    """Get pattern summary."""
    extractor = _get_routine_extractor()
    if not extractor:
        return jsonify({"error": "Routine extractor not available"}), 503
    
    summary = extractor.get_pattern_summary()
    
    return jsonify({
        "ok": True,
        "summary": summary,
    })


@routine_patterns_bp.route("/clear", methods=["POST"])
@require_token
def clear_patterns():
    """Clear all learned patterns."""
    extractor = _get_routine_extractor()
    if not extractor:
        return jsonify({"error": "Routine extractor not available"}), 503
    
    extractor.clear_patterns()
    
    return jsonify({
        "ok": True,
        "message": "Patterns cleared",
    })
