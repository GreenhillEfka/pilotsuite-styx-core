"""Habitus Miner API endpoints for A→B rule discovery."""

import logging
import time
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.habitus_miner.service import HabitusMinerService
from copilot_core.habitus_miner.model import MiningConfig

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
        
        current_app._habitus_service = HabitusMinerService(
            storage_dir=storage_dir,
            config=mining_config
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