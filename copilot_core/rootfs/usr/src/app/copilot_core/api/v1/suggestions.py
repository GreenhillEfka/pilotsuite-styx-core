"""
Suggestions API — Accept, reject, or snooze automation suggestions.

Blueprint prefix: /api/v1/suggestions

Endpoints:
    POST /api/v1/suggestions/accept   — Accept a suggestion
    POST /api/v1/suggestions/reject   — Reject a suggestion
    POST /api/v1/suggestions/snooze   — Snooze a suggestion
    GET  /api/v1/suggestions           — List pending suggestions
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

suggestions_bp = Blueprint(
    "suggestions", __name__, url_prefix="/api/v1/suggestions"
)

# Module-level service reference, set by init_suggestions_api()
_suggestion_engine: Optional[Any] = None

# In-memory store for suggestion states (fallback when no engine is available)
_suggestion_states: Dict[str, str] = {}


def init_suggestions_api(suggestion_engine=None) -> None:
    """Wire the suggestion engine into the blueprint."""
    global _suggestion_engine
    _suggestion_engine = suggestion_engine
    _LOGGER.info("Suggestions API initialized")


@suggestions_bp.route("", methods=["GET"])
def list_suggestions():
    """List pending suggestions."""
    if _suggestion_engine:
        try:
            pending = _suggestion_engine.get_pending(limit=20)
            return jsonify({"ok": True, "suggestions": pending})
        except Exception as exc:
            _LOGGER.exception("Failed to get pending suggestions")
            return jsonify({"ok": False, "error": str(exc)}), 500

    # Fallback: return example suggestions excluding rejected/accepted
    try:
        from copilot_core.example_config import EXAMPLE_SUGGESTIONS
        filtered = [
            s for s in EXAMPLE_SUGGESTIONS
            if _suggestion_states.get(s["id"]) not in ("accepted", "rejected")
        ]
        return jsonify({"ok": True, "suggestions": filtered})
    except Exception:
        return jsonify({"ok": True, "suggestions": []})


@suggestions_bp.route("/accept", methods=["POST"])
@require_token
def accept_suggestion():
    """Accept a suggestion and create the corresponding automation."""
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id", "").strip()

    if not suggestion_id:
        return jsonify({"ok": False, "error": "Missing 'id'"}), 400

    if _suggestion_engine:
        try:
            _suggestion_engine.accept(suggestion_id)
            return jsonify({"ok": True, "id": suggestion_id, "status": "accepted"})
        except Exception as exc:
            _LOGGER.exception("Failed to accept suggestion %s", suggestion_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

    _suggestion_states[suggestion_id] = "accepted"
    return jsonify({"ok": True, "id": suggestion_id, "status": "accepted"})


@suggestions_bp.route("/reject", methods=["POST"])
@require_token
def reject_suggestion():
    """Reject a suggestion permanently."""
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id", "").strip()

    if not suggestion_id:
        return jsonify({"ok": False, "error": "Missing 'id'"}), 400

    if _suggestion_engine:
        try:
            _suggestion_engine.reject(suggestion_id)
            return jsonify({"ok": True, "id": suggestion_id, "status": "rejected"})
        except Exception as exc:
            _LOGGER.exception("Failed to reject suggestion %s", suggestion_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

    _suggestion_states[suggestion_id] = "rejected"
    return jsonify({"ok": True, "id": suggestion_id, "status": "rejected"})


@suggestions_bp.route("/snooze", methods=["POST"])
@require_token
def snooze_suggestion():
    """Snooze a suggestion (show again later)."""
    data = request.get_json(silent=True) or {}
    suggestion_id = data.get("id", "").strip()

    if not suggestion_id:
        return jsonify({"ok": False, "error": "Missing 'id'"}), 400

    if _suggestion_engine:
        try:
            _suggestion_engine.snooze(suggestion_id)
            return jsonify({"ok": True, "id": suggestion_id, "status": "snoozed"})
        except Exception as exc:
            _LOGGER.exception("Failed to snooze suggestion %s", suggestion_id)
            return jsonify({"ok": False, "error": str(exc)}), 500

    _suggestion_states[suggestion_id] = "snoozed"
    return jsonify({"ok": True, "id": suggestion_id, "status": "snoozed"})
