"""API v1 -- Explainability endpoints.

Exposes the ExplainabilityEngine via REST so the frontend and
HACS integration can display *why* a suggestion was made.

Endpoints:
    GET /api/v1/explain/suggestion/<suggestion_id>  -- explain a suggestion
    GET /api/v1/explain/pattern/<pattern_id>         -- explain a habitus pattern
"""
from __future__ import annotations

import logging
from typing import Any

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


def _error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _build_request_payload(*, source_key: str, target_key: str) -> dict[str, str | None]:
    return {
        "source_entity": request.args.get(source_key, ""),
        "target_entity": request.args.get(target_key, ""),
        "time_pattern": request.args.get("time_pattern"),
    }


def _normalize_result(result: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError(f"{label} explanation result must be an object")

    normalized = dict(result)
    normalized["ok"] = True
    return normalized


def _run_explanation(subject_id: str, payload: dict[str, str | None], *, label: str, response_type: str | None = None):
    engine = _get_engine()
    if engine is None:
        return _error("ExplainabilityEngine not initialized", 503)

    try:
        response = _normalize_result(
            engine.explain_suggestion(subject_id, payload),
            label=label,
        )
        if response_type is not None:
            response["type"] = response_type
        return jsonify(response), 200
    except Exception as exc:
        logger.error("Failed to explain %s %s: %s", label, subject_id, exc, exc_info=True)
        return _error(str(exc), 500)


# -- GET /api/v1/explain/suggestion/<suggestion_id> -----------------------

@explain_bp.route("/suggestion/<suggestion_id>", methods=["GET"])
@require_token
def explain_suggestion(suggestion_id: str):
    """Return the causal explanation for a suggestion."""
    return _run_explanation(
        suggestion_id,
        _build_request_payload(source_key="source", target_key="target"),
        label="suggestion",
    )


# -- GET /api/v1/explain/pattern/<pattern_id> ------------------------------

@explain_bp.route("/pattern/<pattern_id>", methods=["GET"])
@require_token
def explain_pattern(pattern_id: str):
    """Return the explanation for a habitus pattern.

    Re-uses the suggestion explainer by treating the pattern's
    antecedent as *source* and consequent as *target*.
    """
    return _run_explanation(
        pattern_id,
        _build_request_payload(source_key="antecedent", target_key="consequent"),
        label="pattern",
        response_type="pattern",
    )
