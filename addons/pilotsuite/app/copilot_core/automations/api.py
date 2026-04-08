"""Automation Suggestions API (v5.9.0)."""

import yaml
from flask import Blueprint, Response, jsonify, request

from ..api.security import require_api_key
from .suggestion_engine import AutomationSuggestionEngine

automations_bp = Blueprint("automations", __name__)

_engine: AutomationSuggestionEngine | None = None


def init_automations_api(engine: AutomationSuggestionEngine) -> None:
    global _engine
    _engine = engine


@automations_bp.route("/api/v1/automations/suggestions", methods=["GET"])
@require_api_key
def get_suggestions():
    """Get automation suggestions.

    Query params:
        category: time, energy, comfort, presence
        include_dismissed: true/false
    """
    if not _engine:
        return jsonify({"error": "Automation engine not initialized"}), 503

    category = request.args.get("category")
    dismissed = request.args.get("include_dismissed", "false").lower() == "true"

    items = _engine.get_suggestions(category=category, include_dismissed=dismissed)
    return jsonify({"ok": True, "count": len(items), "suggestions": items})


@automations_bp.route("/api/v1/automations/suggestions/<suggestion_id>/accept", methods=["POST"])
@require_api_key
def accept_suggestion(suggestion_id: str):
    """Accept a suggestion."""
    if not _engine:
        return jsonify({"error": "Automation engine not initialized"}), 503

    result = _engine.accept_suggestion(suggestion_id)
    if result:
        return jsonify({"ok": True, **result})
    return jsonify({"ok": False, "error": "Suggestion not found"}), 404


@automations_bp.route("/api/v1/automations/suggestions/<suggestion_id>/dismiss", methods=["POST"])
@require_api_key
def dismiss_suggestion(suggestion_id: str):
    """Dismiss a suggestion."""
    if not _engine:
        return jsonify({"error": "Automation engine not initialized"}), 503

    result = _engine.dismiss_suggestion(suggestion_id)
    if result:
        return jsonify({"ok": True, **result})
    return jsonify({"ok": False, "error": "Suggestion not found"}), 404


@automations_bp.route("/api/v1/automations/suggestions/<suggestion_id>/yaml", methods=["GET"])
@require_api_key
def get_suggestion_yaml(suggestion_id: str):
    """Get automation YAML for a suggestion."""
    if not _engine:
        return jsonify({"error": "Automation engine not initialized"}), 503

    automation = _engine.get_suggestion_yaml(suggestion_id)
    if automation:
        return Response(
            yaml.dump(automation, default_flow_style=False, allow_unicode=True, sort_keys=False),
            mimetype="text/yaml",
        )
    return jsonify({"ok": False, "error": "Suggestion not found"}), 404


@automations_bp.route("/api/v1/automations/generate", methods=["POST"])
@require_api_key
def generate_suggestions():
    """Generate suggestions from current data.

    Body: {"schedule": [...], "comfort": {...}, "presence": {...}}
    """
    if not _engine:
        return jsonify({"error": "Automation engine not initialized"}), 503

    body = request.get_json(silent=True) or {}
    generated = []

    # Schedule-based suggestions
    for item in body.get("schedule", []):
        s = _engine.suggest_from_schedule(
            device_type=item.get("device_type", "washer"),
            start_hour=item.get("start_hour", 10),
            end_hour=item.get("end_hour", 12),
            days=item.get("days", "weekday"),
        )
        generated.append(s.id)

    # Solar-based suggestions
    for item in body.get("solar", []):
        s = _engine.suggest_from_solar(
            device_type=item.get("device_type", "ev_charger"),
            surplus_threshold_kwh=item.get("threshold_kwh", 5.0),
        )
        generated.append(s.id)

    # Comfort-based suggestions
    for item in body.get("comfort", []):
        s = _engine.suggest_from_comfort(
            factor=item.get("factor", "co2"),
            threshold=item.get("threshold", 1000),
            action_entity=item.get("entity", "switch.ventilation"),
            action_service=item.get("service", "switch.turn_on"),
        )
        generated.append(s.id)

    # Presence-based suggestions
    if body.get("presence"):
        p = body["presence"]
        s = _engine.suggest_from_presence(
            away_minutes=p.get("away_minutes", 30),
            entities=p.get("entities"),
        )
        generated.append(s.id)

    return jsonify({"ok": True, "generated": len(generated), "ids": generated}), 201
