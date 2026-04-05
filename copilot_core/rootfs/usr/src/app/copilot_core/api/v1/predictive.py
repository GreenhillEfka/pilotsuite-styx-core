"""Predictive Automation API endpoints — v15.3.24.

Contract:
- patterns are learned from observed actions plus live context signals,
- predictive proposals stay read-only until confirmation,
- confirmation materializes the existing policy-gated ActionIntentV1/HA handoff.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.action_closure import get_action_closure_store
from copilot_core.api.security import require_token
from copilot_core.homeassistant.habitat_adapter import wrap_accepted_proposal_action
from copilot_core.homeassistant.habitus_zones import (
    ZoneType,
    evaluate_action_policy,
    infer_module_id_for_action,
    resolve_module_override_for_action,
)
from copilot_core.predictive.automation_engine import (
    PredictiveAutomationEngine,
    create_predictive_automation_engine,
)

_LOGGER = logging.getLogger(__name__)

predictive_bp = Blueprint("predictive", __name__, url_prefix="/api/v1/predictive")

_CONFIDENCE_SCORES = {
    "very_low": 0.1,
    "low": 0.3,
    "medium": 0.5,
    "high": 0.7,
    "very_high": 0.9,
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_zone_type(value: Any) -> ZoneType | None:
    if value in (None, ""):
        return None
    try:
        return ZoneType(str(value))
    except ValueError as exc:  # pragma: no cover - exercised via API contract tests
        raise ValueError(f"Invalid zone_type: {value}") from exc


def _build_service_call_preview(action: dict[str, Any]) -> dict[str, Any]:
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    entity_id = str(action.get("entity_id") or target.get("entity_id") or "").strip()
    if entity_id and "entity_id" not in target:
        target = {**target, "entity_id": entity_id}

    return {
        "domain": str(action.get("domain") or "").strip().lower(),
        "service": str(action.get("suggested_service") or action.get("service") or "").strip().lower(),
        "target": target,
        "expected_state": action.get("state"),
    }


def _confidence_score(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return _CONFIDENCE_SCORES.get(str(value or "").strip().lower(), 0.0)


def _get_predictive_engine() -> PredictiveAutomationEngine:
    services = current_app.config.get("COPILOT_SERVICES", {})
    if isinstance(services, dict):
        for key in ("predictive_engine", "predictive_automation_engine"):
            engine = services.get(key)
            if isinstance(engine, PredictiveAutomationEngine):
                return engine

    engine = getattr(current_app, "_predictive_engine", None)
    if isinstance(engine, PredictiveAutomationEngine):
        return engine

    engine = create_predictive_automation_engine()
    current_app._predictive_engine = engine
    return engine


def _collect_context(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    args = request.args
    away_events = payload.get("away_events")
    if not isinstance(away_events, list):
        away_events = []
        if _parse_bool(payload.get("away_event") or args.get("away_event")):
            away_events = [payload.get("calendar_summary") or args.get("calendar_summary") or "away_event"]

    context = {
        "presence_detected": _parse_bool(payload.get("presence_detected") or args.get("presence_detected")),
        "calendar_summary": payload.get("calendar_summary") or payload.get("calendar_event") or args.get("calendar_summary"),
        "calendar_event": payload.get("calendar_event") or args.get("calendar_event"),
        "away_events": away_events,
        "weather_condition": payload.get("weather_condition") or args.get("weather"),
        "current_temperature": payload.get("current_temperature") or args.get("temperature", type=float),
    }
    return {key: value for key, value in context.items() if value not in (None, "", [])}


def _normalize_action_payload(entity_id: str, action: Any) -> dict[str, Any]:
    if isinstance(action, dict):
        return dict(action)

    service = str(action or "").strip().lower()
    domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
    return {
        "domain": domain,
        "service": service,
        "entity_id": entity_id,
    }


def _materialize_confirmation_response(proposal: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal_id") or "").strip()
    zone_id = str(payload.get("zone_id") or proposal.get("zone_id") or "").strip()
    action = proposal.get("predicted_action") if isinstance(proposal.get("predicted_action"), dict) else {}
    if not proposal_id or not zone_id or not action:
        raise ValueError("proposal_id, zone_id, and predicted_action are required")

    zone_type = _normalize_zone_type(payload.get("zone_type") or proposal.get("zone_type"))
    module_id = str(
        payload.get("module_id")
        or proposal.get("module_id")
        or infer_module_id_for_action(action)
        or ""
    ).strip() or None

    module_overrides = payload.get("module_overrides") if isinstance(payload.get("module_overrides"), dict) else proposal.get("module_overrides")
    module_override = (
        payload.get("module_override")
        if isinstance(payload.get("module_override"), dict)
        else resolve_module_override_for_action(zone_type, module_id, module_overrides)
    )
    explicit_styx_instruction = bool(payload.get("styx_instruction") or payload.get("execute_now"))
    policy_gate = evaluate_action_policy(
        module_id,
        module_override,
        explicit_styx_instruction=explicit_styx_instruction,
    )

    accepted_at = _utcnow()
    action_preview = _build_service_call_preview(action)
    action_seed = f"{proposal_id}|{zone_id}|{module_id or 'unknown'}|predictive"
    action_intent_id = f"action:{hashlib.sha1(action_seed.encode('utf-8')).hexdigest()[:12]}"

    proposal_intent = {
        "contract": "ProposalIntentV1",
        "proposal_id": proposal_id,
        "zone_id": zone_id,
        "module_id": module_id,
        "state": "accepted",
        "accepted_at": accepted_at,
        "title": proposal.get("description"),
        "summary": proposal.get("reasoning"),
        "confidence": proposal.get("confidence_score"),
        "source": "predictive.accepted",
    }
    action_intent = {
        "contract": "ActionIntentV1",
        "action_intent_id": action_intent_id,
        "proposal_id": proposal_id,
        "zone_id": zone_id,
        "module_id": module_id,
        "source": "predictive.accepted",
        "execution_state": policy_gate["execution_state"],
        "eligible_for_execution": policy_gate["eligible_for_execution"],
        "needs_explicit_styx_instruction": policy_gate["needs_explicit_styx_instruction"],
        "blocked_reasons": policy_gate["blocked_reasons"],
        "accepted_at": accepted_at,
        "action": action_preview,
        "policy": policy_gate,
    }
    habitat_module_command = {
        "contract": "HabitatModuleCommandV1",
        "module_id": module_id,
        "output_adapter": str(module_override.get("output_adapter") or "homeassistant") if isinstance(module_override, dict) else "homeassistant",
        "command_mode": "service_call_ready" if policy_gate["eligible_for_execution"] else "preview_only",
        "service_call": action_preview,
        "blocked_reasons": policy_gate["blocked_reasons"],
    }
    ha_output = wrap_accepted_proposal_action(
        action_id=action_intent_id,
        proposal_id=proposal_id,
        module_id=module_id or "unknown",
        zone_id=zone_id,
        service_call=action_preview,
        confidence=float(proposal.get("confidence_score") or 0.0),
        explanation=str(proposal.get("reasoning") or proposal.get("description") or ""),
        accepted_at=accepted_at,
        source="predictive.accepted",
        policy_gate=policy_gate,
    )
    action_closure = get_action_closure_store().upsert(
        source="predictive.accepted",
        proposal_id=proposal_id,
        action_id=action_intent_id,
        proposal_intent=proposal_intent,
        action_intent=action_intent,
        zone_id=zone_id,
        module_id=module_id,
        service_call=action_preview,
        policy_gate=policy_gate,
        accepted_at=accepted_at,
        metadata={
            "surface": "predictive",
            "pattern_id": proposal.get("pattern_id"),
        },
    )

    return {
        "status": "ok",
        "proposal": proposal,
        "proposal_intent": proposal_intent,
        "action_intent": action_intent,
        "action_closure": action_closure,
        "habitat_module_command": habitat_module_command,
        "ha_output": ha_output,
        "policy_gate": policy_gate,
    }


@predictive_bp.route("/patterns", methods=["GET"])
@require_token
def get_patterns():
    """Return learned predictive patterns from the canonical engine."""
    try:
        engine = _get_predictive_engine()
        pattern_type = request.args.get("type")
        entity_id = request.args.get("entity_id")
        min_confidence = request.args.get("min_confidence", type=float)

        patterns = engine.get_patterns()
        if pattern_type:
            patterns = [pattern for pattern in patterns if pattern.get("pattern_type") == pattern_type]
        if entity_id:
            patterns = [pattern for pattern in patterns if pattern.get("entity_id") == entity_id]
        if min_confidence is not None:
            patterns = [
                pattern for pattern in patterns
                if _confidence_score(pattern.get("confidence")) >= float(min_confidence)
            ]

        return jsonify({
            "ok": True,
            "patterns": patterns,
            "count": len(patterns),
            "generated_at": _utcnow(),
        })
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Error getting predictive patterns: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@predictive_bp.route("/next", methods=["GET"])
@require_token
def get_next_prediction():
    """Return the next predictive proposal(s) for the current live context."""
    try:
        engine = _get_predictive_engine()
        max_predictions = max(int(request.args.get("max_predictions", 1)), 1)
        predictions = engine.generate_predictions(context=_collect_context())[:max_predictions]
        payloads = [prediction.to_dict() for prediction in predictions]

        return jsonify({
            "ok": True,
            "prediction": payloads[0] if payloads else None,
            "all_predictions": payloads,
            "count": len(payloads),
            "generated_at": _utcnow(),
        })
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Error getting next predictive proposal: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@predictive_bp.route("/confirm", methods=["POST"])
@require_token
def confirm_prediction():
    """Accept a predictive proposal and materialize a policy-gated action intent."""
    try:
        engine = _get_predictive_engine()
        payload = request.get_json(silent=True) or {}
        proposal_id = str(payload.get("proposal_id") or "").strip()
        if not proposal_id:
            return jsonify({"ok": False, "error": "proposal_id required"}), 400

        if not engine.accept_prediction(proposal_id):
            return jsonify({"ok": False, "error": "Prediction not found"}), 404

        proposal = engine.get_proposal(proposal_id)
        if proposal is None:
            return jsonify({"ok": False, "error": "Prediction not found"}), 404

        return jsonify(_materialize_confirmation_response(proposal.to_dict(), payload))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Error confirming prediction: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@predictive_bp.route("/reject", methods=["POST"])
@require_token
def reject_prediction():
    """Reject a predictive proposal and persist optional feedback."""
    try:
        engine = _get_predictive_engine()
        payload = request.get_json(silent=True) or {}
        proposal_id = str(payload.get("proposal_id") or "").strip()
        feedback = payload.get("feedback") or payload.get("reason")
        if not proposal_id:
            return jsonify({"ok": False, "error": "proposal_id required"}), 400

        if not engine.reject_prediction(proposal_id, feedback=feedback):
            return jsonify({"ok": False, "error": "Prediction not found"}), 404

        proposal = engine.get_proposal(proposal_id)
        return jsonify({
            "ok": True,
            "proposal_id": proposal_id,
            "feedback": feedback,
            "proposal": proposal.to_dict() if proposal else None,
            "generated_at": _utcnow(),
        })
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Error rejecting prediction: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@predictive_bp.route("/stats", methods=["GET"])
@require_token
def get_predictive_stats():
    """Return aggregate predictive-engine statistics."""
    try:
        engine = _get_predictive_engine()
        return jsonify({
            "ok": True,
            "stats": engine.get_stats(),
            "generated_at": _utcnow(),
        })
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Error getting predictive stats: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@predictive_bp.route("/observe", methods=["POST"])
@require_token
def observe_action():
    """Observe a user action so the predictive engine can learn new patterns."""
    try:
        engine = _get_predictive_engine()
        payload = request.get_json(silent=True) or {}
        entity_id = str(payload.get("entity_id") or "").strip()
        action = payload.get("action")
        if not entity_id or action in (None, ""):
            return jsonify({"ok": False, "error": "entity_id and action required"}), 400

        action_payload = _normalize_action_payload(entity_id, action)
        patterns_before = len(engine.get_patterns())
        engine.record_action({
            "entity_id": entity_id,
            "zone_id": payload.get("zone_id"),
            "module_id": payload.get("module_id"),
            "timestamp": payload.get("timestamp"),
            "action": action_payload,
            "context": payload.get("context") if isinstance(payload.get("context"), dict) else {},
        })
        stats = engine.get_stats()

        return jsonify({
            "ok": True,
            "message": "Beobachtung registriert",
            "patterns_updated": stats["patterns_total"] - patterns_before,
            "stats": stats,
        })
    except Exception as exc:  # pragma: no cover - defensive
        _LOGGER.error("Error observing predictive action: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── SLICE 136: Predictive-Analytics Expansion ─────────────────────────────────

@predictive_bp.get("/suggestions")
def predictive_suggestions():
    """Get ML-based predictive suggestions.
    
    Returns actions the system predicts the user will want based on:
    - Time of day
    - Historical patterns
    - Current context (mood, zone, presence)
    - Weather/external factors
    
    Query params:
    - limit: Max suggestions (default 5)
    - confidence_min: Minimum confidence threshold (default 0.5)
    """
    from copilot_core.predictive.automation_engine import get_automation_engine
    
    try:
        limit = int(request.args.get("limit", "5"))
    except (ValueError, TypeError):
        limit = 5
    
    try:
        confidence_min = float(request.args.get("confidence_min", "0.5"))
    except (ValueError, TypeError):
        confidence_min = 0.5
    
    limit = max(1, min(limit, 20))
    confidence_min = max(0.0, min(confidence_min, 1.0))
    
    try:
        engine = get_automation_engine()
        suggestions = engine.get_predictive_suggestions(
            limit=limit,
            confidence_min=confidence_min
        )
    except Exception as e:
        _LOGGER.warning("Failed to get predictive suggestions: %s", e)
        suggestions = []
    
    return jsonify({
        "ok": True,
        "suggestions": suggestions,
        "count": len(suggestions),
        "limit": limit,
        "confidence_min": confidence_min
    })


@predictive_bp.get("/anomalies")
def predictive_anomalies():
    """Get anomaly detection alerts.
    
    Returns unusual patterns detected in:
    - Energy consumption
    - Presence patterns
    - Module usage
    - Mood transitions
    
    Query params:
    - hours: Time range (default 24)
    - severity: min|moderate|severe (default: moderate)
    """
    from copilot_core.predictive.automation_engine import get_automation_engine
    
    try:
        hours = int(request.args.get("hours", "24"))
    except (ValueError, TypeError):
        hours = 24
    
    severity = request.args.get("severity", "moderate")
    
    hours = max(1, min(hours, 720))
    
    try:
        engine = get_automation_engine()
        anomalies = engine.get_anomalies(hours=hours, severity=severity)
    except Exception as e:
        _LOGGER.warning("Failed to get anomalies: %s", e)
        anomalies = []
    
    return jsonify({
        "ok": True,
        "anomalies": anomalies,
        "count": len(anomalies),
        "hours": hours,
        "severity": severity
    })


@predictive_bp.get("/learning-progress")
def predictive_learning_progress():
    """Get model learning progress and accuracy metrics.
    
    Returns:
    - model_accuracy: Current prediction accuracy
    - training_samples: Number of samples learned
    - improvement_rate: Accuracy improvement over time
    - last_updated: Last training timestamp
    """
    from copilot_core.predictive.automation_engine import get_automation_engine
    
    try:
        engine = get_automation_engine()
        progress = engine.get_learning_progress()
    except Exception as e:
        _LOGGER.warning("Failed to get learning progress: %s", e)
        progress = {
            "model_accuracy": 0.0,
            "training_samples": 0,
            "improvement_rate": 0.0,
            "last_updated": None
        }
    
    return jsonify({
        "ok": True,
        "progress": progress,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
