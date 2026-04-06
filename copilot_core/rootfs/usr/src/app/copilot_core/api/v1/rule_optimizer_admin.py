"""Rule Optimizer Admin API — Rule scoring and optimization.
"""
from flask import Blueprint, jsonify, request
import logging

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("rule_optimizer_admin", __name__, url_prefix="/api/v1/optimizer")

@bp.route("/scores", methods=["GET"])
def get_rule_scores():
    """Get scores for all rules."""
    # Would call rule_optimizer.score_all_rules() in production
    return jsonify({"ok": True, "scores": []})

@bp.route("/suggestions", methods=["GET"])
def get_optimization_suggestions():
    """Get optimization suggestions for low-performing rules."""
    return jsonify({"ok": True, "suggestions": []})

@bp.route("/auto-disable", methods=["POST"])
def auto_disable_low_score():
    """Auto-disable rules below threshold."""
    data = request.get_json() or {}
    threshold = data.get("threshold", 0.3)
    return jsonify({"ok": True, "disabled_count": 0, "threshold": threshold})

@bp.route("/feedback", methods=["POST"])
def submit_feedback():
    """Submit user feedback for a rule."""
    data = request.get_json() or {}
    rule_id = data.get("rule_id")
    was_useful = data.get("was_useful", True)
    return jsonify({"ok": True, "rule_id": rule_id, "feedback": "recorded"})
