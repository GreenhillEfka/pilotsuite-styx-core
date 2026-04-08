"""API v1 -- Explainability endpoints.

Exposes the ExplainabilityEngine via REST so the frontend and
HACS integration can display *why* a suggestion was made.

Endpoints:
    GET /api/v1/explain/suggestion/<suggestion_id>  -- explain a suggestion
    GET /api/v1/explain/pattern/<pattern_id>         -- explain a habitus pattern
"""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

explain_bp = Blueprint("explain", __name__, url_prefix="/api/v1/explain")

_engine = None


def init_explain_api(engine) -> None:
    """Inject the ExplainabilityEngine singleton at startup."""
    global _engine
    _engine = engine
    logger.info("Explain API initialized")


def _get_engine():
    if _engine is None:
        return None
    return _engine


# -- GET /api/v1/explain/suggestion/<suggestion_id> -----------------------

@explain_bp.route("/suggestion/<suggestion_id>", methods=["GET"])
@require_token
def explain_suggestion(suggestion_id: str):
    """Return the causal explanation for a suggestion."""
    engine = _get_engine()
    if engine is None:
        return jsonify({"ok": False, "error": "ExplainabilityEngine not initialized"}), 503

    suggestion_data = {
        "source_entity": request.args.get("source", ""),
        "target_entity": request.args.get("target", ""),
        "time_pattern": request.args.get("time_pattern"),
    }

    try:
        result = engine.explain_suggestion(suggestion_id, suggestion_data)
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        logger.error("Failed to explain suggestion %s: %s", suggestion_id, exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500


# -- GET /api/v1/explain/pattern/<pattern_id> ------------------------------

@explain_bp.route("/pattern/<pattern_id>", methods=["GET"])
@require_token
def explain_pattern(pattern_id: str):
    """Return the explanation for a habitus pattern.

    Re-uses the suggestion explainer by treating the pattern's
    antecedent as *source* and consequent as *target*.
    """
    engine = _get_engine()
    if engine is None:
        return jsonify({"ok": False, "error": "ExplainabilityEngine not initialized"}), 503

    pattern_data = {
        "source_entity": request.args.get("antecedent", ""),
        "target_entity": request.args.get("consequent", ""),
        "time_pattern": request.args.get("time_pattern"),
    }

    try:
        result = engine.explain_suggestion(pattern_id, pattern_data)
        result["type"] = "pattern"
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        logger.error("Failed to explain pattern %s: %s", pattern_id, exc, exc_info=True)
        return jsonify({"ok": False, "error": str(exc)}), 500
