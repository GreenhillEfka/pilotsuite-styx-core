"""Predictive Symbiosis Admin API — ML-based insights.
"""
from flask import Blueprint, jsonify, request
import logging

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("predictive_admin", __name__, url_prefix="/api/v1/predictive")

# In-memory store for demo
_patterns = []
_suggestions = []

@bp.route("/patterns", methods=["GET"])
def list_patterns():
    return jsonify({"ok": True, "patterns": _patterns, "count": len(_patterns)})

@bp.route("/analyze", methods=["POST"])
def analyze_patterns():
    """Trigger pattern analysis on current event history."""
    # Would call predictive_engine.analyze_patterns() in production
    return jsonify({"ok": True, "status": "analyzing", "message": "Pattern analysis triggered"})

@bp.route("/suggestions", methods=["GET"])
def get_rule_suggestions():
    """Get ML-generated rule suggestions."""
    return jsonify({"ok": True, "suggestions": _suggestions})

@bp.route("/suggestions/<pattern_id>/accept", methods=["POST"])
def accept_suggestion(pattern_id):
    """Accept a pattern suggestion and create a rule."""
    _suggestions.append({"pattern_id": pattern_id, "accepted": True})
    return jsonify({"ok": True, "pattern_id": pattern_id, "status": "accepted"})

@bp.route("/stats", methods=["GET"])
def get_stats():
    return jsonify({
        "ok": True,
        "stats": {
            "total_patterns": len(_patterns),
            "total_suggestions": len(_suggestions),
            "accepted_suggestions": sum(1 for s in _suggestions if s.get("accepted"))
        }
    })
