"""Habitus Miner API endpoints for A→B rule discovery."""

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.habitus_miner.service import HabitusMinerService
from copilot_core.habitus_miner.model import MiningConfig
from copilot_core.homeassistant.habitat_adapter import wrap_accepted_proposal_action
from copilot_core.homeassistant.habitus_zones import (
    ZoneType,
    evaluate_action_policy,
    infer_module_id_for_action,
    resolve_module_override_for_action,
)

_LOGGER = logging.getLogger(__name__)

bp = Blueprint("habitus", __name__, url_prefix="/habitus")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


def _get_service() -> HabitusMinerService:
    """Get or create habitus miner service instance."""
    if not hasattr(current_app, '_habitus_service'):
        cfg = current_app.config["COPILOT_CFG"]
        storage_dir = Path(cfg.data_dir) / "habitus_miner"
        
        # Create default config (can be overridden via API)
        mining_config = MiningConfig()
        
        # Pass RAG and bus services for pattern embedding + event publishing
        copilot_services = current_app.config.get("COPILOT_SERVICES", {})
        current_app._habitus_service = HabitusMinerService(
            storage_dir=storage_dir,
            config=mining_config,
            vector_store=copilot_services.get("vector_store") if isinstance(copilot_services, dict) else None,
            embedding_engine=copilot_services.get("embedding_engine") if isinstance(copilot_services, dict) else None,
            integration_bus=copilot_services.get("integration_bus") if isinstance(copilot_services, dict) else None,
        )
    
    return current_app._habitus_service


@bp.route("/status", methods=["GET"])
def get_status():
    """Get habitus miner status and statistics."""
    try:
        service = _get_service()
        stats = service.store.get_stats()
        
        return jsonify({
            "status": "ok",
            "version": "0.1.0",
            "statistics": stats,
            "config": {
                "windows": service.config.windows,
                "min_support_A": service.config.min_support_A,
                "min_hits": service.config.min_hits,
                "min_confidence": service.config.min_confidence,
                "min_lift": service.config.min_lift,
                "max_rules": service.config.max_rules,
            }
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get habitus status: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/health", methods=["GET"])
def get_health():
    """Health check alias for /status (HA Integration compatibility)."""
    return get_status()


@bp.route("/rules", methods=["GET"])
def get_rules():
    """Get discovered A→B rules with optional filtering."""
    try:
        service = _get_service()
        
        # Parse query parameters
        limit = request.args.get("limit", type=int)
        min_score = request.args.get("min_score", type=float)
        a_filter = request.args.get("a_filter")
        b_filter = request.args.get("b_filter")
        domain_filter = request.args.get("domain_filter")
        
        rules = service.get_rules(
            limit=limit,
            min_score=min_score,
            a_filter=a_filter,
            b_filter=b_filter,
            domain_filter=domain_filter
        )
        
        # Convert to JSON-serializable format
        rules_data = []
        for rule in rules:
            rule_data = {
                "A": rule.A,
                "B": rule.B,
                "dt_sec": rule.dt_sec,
                "nA": rule.nA,
                "nB": rule.nB,
                "nAB": rule.nAB,
                "confidence": round(rule.confidence, 3),
                "confidence_lb": round(rule.confidence_lb, 3),
                "lift": round(rule.lift, 2),
                "leverage": round(rule.leverage, 3),
                "score": round(rule.score(), 3),
                "observation_period_days": rule.observation_period_days,
                "created_at_ms": rule.created_at_ms,
            }
            
            # Add evidence if available
            if rule.evidence:
                rule_data["evidence"] = {
                    "hit_examples": rule.evidence.hit_examples[:3],  # Limit for API
                    "miss_examples": rule.evidence.miss_examples[:3],
                    "latency_quantiles": [round(x, 1) for x in rule.evidence.latency_quantiles],
                }
            
            rules_data.append(rule_data)
        
        return jsonify({
            "status": "ok",
            "total_rules": len(rules_data),
            "rules": rules_data
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get rules: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/rules/summary", methods=["GET"])
def get_rules_summary():
    """Get rules summary with domain statistics."""
    try:
        service = _get_service()
        summary = service.export_rules_summary()
        
        return jsonify({
            "status": "ok", 
            **summary
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get rules summary: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/rules/<path:rule_key>/explain", methods=["GET"])
def explain_rule(rule_key: str):
    """Get human-readable explanation for a specific rule."""
    try:
        service = _get_service()
        
        # Find rule by A→B key
        # Format: "entity.id:transition->entity.id:transition"
        if "->" not in rule_key:
            return jsonify({"status": "error", "message": "Invalid rule key format"}), 400
        
        a_key, b_key = rule_key.split("->", 1)
        
        rules = service.get_rules()
        rule = None
        for r in rules:
            if r.A == a_key and r.B == b_key:
                rule = r
                break
        
        if not rule:
            return jsonify({"status": "error", "message": "Rule not found"}), 404
        
        explanation = service.explain_rule(rule)
        
        return jsonify({
            "status": "ok",
            "rule_key": rule_key,
            "explanation": explanation
        })
    
    except Exception as e:
        _LOGGER.error("Failed to explain rule %s: %s", rule_key, e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/mine", methods=["POST"])
def mine_rules():
    """Mine rules from provided Home Assistant events."""
    try:
        data = request.get_json()
        if not data or "events" not in data:
            return jsonify({"status": "error", "message": "Missing 'events' in request"}), 400
        
        ha_events = data["events"]
        if not isinstance(ha_events, list):
            return jsonify({"status": "error", "message": "Events must be a list"}), 400
        
        # Optional: update config for this mining run
        mining_config = None
        if "config" in data:
            service = _get_service()
            # Create temporary config override
            mining_config = MiningConfig(**data["config"])
            original_config = service.config
            service.config = mining_config
        
        service = _get_service()
        start_time = time.time()
        
        rules = service.mine_from_ha_events(ha_events)
        
        mining_time = time.time() - start_time
        
        # Restore original config if we overrode it
        if mining_config and 'original_config' in locals():
            service.config = original_config
        
        return jsonify({
            "status": "ok",
            "mining_time_sec": round(mining_time, 2),
            "total_input_events": len(ha_events),
            "discovered_rules": len(rules),
            "top_rules": [
                {
                    "A": rule.A,
                    "B": rule.B,
                    "confidence": round(rule.confidence, 3),
                    "lift": round(rule.lift, 2),
                    "dt_sec": rule.dt_sec,
                }
                for rule in rules[:10]
            ]
        })
    
    except Exception as e:
        _LOGGER.error("Failed to mine rules: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


def _normalize_zone_type(value: Any) -> ZoneType | None:
    if value in (None, ""):
        return None
    try:
        return ZoneType(str(value))
    except ValueError as exc:
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


@bp.route("/zone-proposals", methods=["GET", "POST"])
def get_zone_proposals():
    """Get explainable automation proposals for habitus zones.

    Uses cached normalized events by default. POST may provide raw HA events via
    ``{"events": [...]}`` to generate proposals on demand.
    """
    try:
        payload = request.get_json(silent=True) if request.method == "POST" else None
        payload = payload or {}

        limit = payload.get("limit", request.args.get("limit", type=int) or 10)
        min_confidence = payload.get("min_confidence", request.args.get("min_confidence", type=float) or 0.55)
        zone_id = payload.get("zone_id") or request.args.get("zone_id")

        service = _get_service()
        copilot_services = current_app.config.get("COPILOT_SERVICES", {})
        tag_zone_integration = (
            copilot_services.get("tag_zone_integration")
            if isinstance(copilot_services, dict)
            else None
        )
        if tag_zone_integration is None:
            return jsonify({
                "status": "error",
                "message": "TagZoneIntegration unavailable; cannot build zone proposals",
            }), 503

        events = None
        if isinstance(payload.get("events"), list):
            events = service.process_ha_events(payload["events"])

        result = service.get_zone_proposals(
            tag_zone_integration=tag_zone_integration,
            events=events,
            zone_id=zone_id,
            limit=int(limit),
            min_confidence=float(min_confidence),
        )
        return jsonify(result)

    except Exception as e:
        _LOGGER.error("Failed to get zone proposals: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/zone-proposals/accept", methods=["POST"])
def accept_zone_proposal():
    """Turn an accepted proposal into an action intent without forcing execution."""
    try:
        data = request.get_json(silent=True) or {}
        proposal = data.get("proposal") if isinstance(data.get("proposal"), dict) else data

        if not isinstance(proposal, dict):
            return jsonify({"status": "error", "message": "Missing proposal payload"}), 400

        proposal_id = str(proposal.get("proposal_id") or proposal.get("id") or "").strip()
        zone_id = str(proposal.get("zone_id") or data.get("zone_id") or "").strip()
        action = proposal.get("action") if isinstance(proposal.get("action"), dict) else {}

        if not proposal_id or not zone_id or not action:
            return jsonify({
                "status": "error",
                "message": "proposal_id, zone_id, and action are required",
            }), 400

        try:
            zone_type = _normalize_zone_type(data.get("zone_type") or proposal.get("zone_type"))
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

        module_id = str(
            data.get("module_id")
            or proposal.get("module_id")
            or infer_module_id_for_action(action)
            or ""
        ).strip() or None

        module_overrides = data.get("module_overrides") if isinstance(data.get("module_overrides"), dict) else proposal.get("module_overrides")
        module_override = (
            data.get("module_override")
            if isinstance(data.get("module_override"), dict)
            else resolve_module_override_for_action(zone_type, module_id, module_overrides)
        )
        explicit_styx_instruction = bool(data.get("styx_instruction") or data.get("execute_now"))
        policy_gate = evaluate_action_policy(
            module_id,
            module_override,
            explicit_styx_instruction=explicit_styx_instruction,
        )

        accepted_at = datetime.now(timezone.utc).isoformat()
        action_preview = _build_service_call_preview(action)
        action_seed = f"{proposal_id}|{zone_id}|{module_id or 'unknown'}"
        action_intent_id = f"action:{hashlib.sha1(action_seed.encode('utf-8')).hexdigest()[:12]}"

        proposal_intent = {
            "contract": "ProposalIntentV1",
            "proposal_id": proposal_id,
            "zone_id": zone_id,
            "module_id": module_id,
            "state": "accepted",
            "accepted_at": accepted_at,
            "title": proposal.get("title"),
            "summary": proposal.get("summary"),
            "confidence": proposal.get("confidence"),
        }
        action_intent = {
            "contract": "ActionIntentV1",
            "action_intent_id": action_intent_id,
            "proposal_id": proposal_id,
            "zone_id": zone_id,
            "module_id": module_id,
            "source": "proposal.accepted",
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
            confidence=float(proposal.get("confidence") or 0.0),
            explanation=str(proposal.get("summary") or proposal.get("title") or ""),
            accepted_at=accepted_at,
            source="proposal.accepted",
            policy_gate=policy_gate,
        )

        return jsonify({
            "status": "ok",
            "proposal_intent": proposal_intent,
            "action_intent": action_intent,
            "habitat_module_command": habitat_module_command,
            "ha_output": ha_output,
            "policy_gate": policy_gate,
        })

    except Exception as e:
        _LOGGER.error("Failed to accept zone proposal: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/config", methods=["GET"])
def get_config():
    """Get current mining configuration."""
    try:
        service = _get_service()
        config = service.config
        
        return jsonify({
            "status": "ok",
            "config": {
                "windows": config.windows,
                "min_support_A": config.min_support_A,
                "min_support_B": config.min_support_B,
                "min_hits": config.min_hits,
                "min_confidence": config.min_confidence,
                "min_confidence_lb": config.min_confidence_lb,
                "min_lift": config.min_lift,
                "min_leverage": config.min_leverage,
                "max_rules": config.max_rules,
                "max_evidence_examples": config.max_evidence_examples,
                "default_cooldown": config.default_cooldown,
                "context_features": config.context_features,
                "include_domains": config.include_domains,
                "exclude_domains": config.exclude_domains,
                "exclude_self_rules": config.exclude_self_rules,
                "exclude_same_entity": config.exclude_same_entity,
                "min_stability_days": config.min_stability_days,
                "anonymize_entity_ids": config.anonymize_entity_ids,
            }
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get config: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/config", methods=["POST"])
def update_config():
    """Update mining configuration."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Missing configuration data"}), 400
        
        service = _get_service()
        service.update_config(**data)
        
        return jsonify({"status": "ok", "message": "Configuration updated"})
    
    except Exception as e:
        _LOGGER.error("Failed to update config: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/feedback", methods=["POST"])
def rule_feedback():
    """Apply user feedback (accepted/rejected/snoozed) to a rule.

    Body: {"rule_a": "...", "rule_b": "...", "accepted": true/false}
      or: {"rule_a": "...", "rule_b": "...", "action": "accepted"|"rejected"|"snoozed"}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Missing request body"}), 400

        rule_a = data.get("rule_a", "")
        rule_b = data.get("rule_b", "")

        # Support both legacy "accepted" bool and new "action" string
        action = data.get("action")
        accepted = data.get("accepted")

        if action == "snoozed":
            # Snoozed: record in feedback store only, don't adjust rule counts
            if not rule_a or not rule_b:
                return jsonify({"status": "error", "message": "Missing rule_a or rule_b"}), 400
            service = _get_service()
            pattern_key = f"{rule_a}->{rule_b}"
            service.feedback_store.record_feedback(pattern_key, "snoozed")
            return jsonify({"status": "ok", "message": "Feedback recorded (snoozed)"})

        if action is not None:
            accepted = action == "accepted"
        elif accepted is None:
            return jsonify({"status": "error", "message": "Missing accepted or action"}), 400

        if not rule_a or not rule_b:
            return jsonify({"status": "error", "message": "Missing rule_a or rule_b"}), 400

        service = _get_service()
        updated = service.apply_feedback(rule_a, rule_b, bool(accepted))

        if not updated:
            return jsonify({"status": "error", "message": "Rule not found"}), 404

        return jsonify({"status": "ok", "message": "Feedback applied"})

    except Exception as e:
        _LOGGER.error("Failed to apply feedback: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route("/reset", methods=["POST"])
def reset_cache():
    """Reset all cached data and discovered rules."""
    try:
        service = _get_service()
        service.reset_cache()
        
        return jsonify({"status": "ok", "message": "Cache reset successfully"})
    
    except Exception as e:
        _LOGGER.error("Failed to reset cache: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500