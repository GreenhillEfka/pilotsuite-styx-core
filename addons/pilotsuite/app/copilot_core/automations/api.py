"""Automation Suggestions API (v5.9.0)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import yaml
from flask import Blueprint, Response, jsonify, request

from ..api.security import require_api_key
from ..energy.solar_surplus_optimizer import SolarSurplusOptimizer
from .suggestion_engine import AutomationSuggestionEngine

automations_bp = Blueprint("automations_suggestions", __name__)

_engine: AutomationSuggestionEngine | None = None


def _parse_optional_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _generate_solar_surplus_batch(batch: dict[str, Any]) -> dict[str, Any]:
    optimizer = SolarSurplusOptimizer()
    report = optimizer.get_recommendations_as_dict(
        pv_forecast=batch.get("pv_forecast") or [],
        shiftable_devices=batch.get("shiftable_devices") or [],
        load_forecast=batch.get("load_forecast") or [],
        price_forecast=batch.get("price_forecast") or [],
        reference_time=_parse_optional_timestamp(batch.get("reference_time")),
        now=_parse_optional_timestamp(batch.get("now")),
        default_import_price_ct_kwh=float(batch.get("default_import_price_ct_kwh", 30.0)),
        default_export_price_ct_kwh=float(batch.get("default_export_price_ct_kwh", 8.0)),
    )

    suggestion_ids: list[str] = []
    shiftable_by_id = {
        str(item.get("device_id")): item
        for item in (batch.get("shiftable_devices") or [])
        if isinstance(item, dict) and item.get("device_id")
    }

    for recommendation in report["recommendations"]:
        if recommendation.get("action") not in {"schedule_now", "schedule_at"}:
            continue
        device = shiftable_by_id.get(str(recommendation.get("device_id")), {})
        suggestion = _engine.suggest_from_solar_surplus_recommendation(
            recommendation,
            device_type=device.get("device_type"),
            entity_id=device.get("entity_id"),
        )
        suggestion_ids.append(suggestion.id)

    return {
        **report,
        "suggestion_ids": suggestion_ids,
        "generated": len(suggestion_ids),
    }


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

    Body: {"schedule": [...], "solar": [...], "solar_surplus_batches": [...], ...}
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

    solar_surplus_batches = []
    for batch in body.get("solar_surplus_batches", []):
        if not isinstance(batch, dict):
            continue
        result = _generate_solar_surplus_batch(batch)
        solar_surplus_batches.append(result)
        generated.extend(result["suggestion_ids"])

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

    response = {"ok": True, "generated": len(generated), "ids": generated}
    if solar_surplus_batches:
        response["solar_surplus_batches"] = solar_surplus_batches
    return jsonify(response), 201
