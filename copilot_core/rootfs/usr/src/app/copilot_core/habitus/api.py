"""
Habitus API endpoints - Pattern mining REST interface.

Provides HTTP API for habitus pattern discovery and candidate management:
- POST /api/v1/habitus/mine - Trigger pattern mining
- GET /api/v1/habitus/stats - Mining statistics  
- GET /api/v1/habitus/patterns - Recent patterns
- GET  /api/v1/habitus/config - Read persisted miner configuration
- POST /api/v1/habitus/config - Update persisted miner configuration
"""
import time
import logging
from typing import Optional, Dict, Any, List
from flask import Blueprint, request, jsonify, Response

from .service import HabitusService
from ..api.security import require_api_key
from ..brain_graph import BrainGraphService

logger = logging.getLogger(__name__)

# Create blueprint
habitus_bp = Blueprint('habitus_svc', __name__, url_prefix='/api/v1/habitus')

# Global service instances (will be initialized in main.py)
_habitus_service: HabitusService = None
_brain_graph_service: BrainGraphService = None


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_rule_from_pattern(pattern: Dict[str, Any]) -> Dict[str, Any]:
    """Map persisted pattern candidate data to a stable rule schema."""
    metadata = pattern.get("metadata") or {}
    evidence = pattern.get("evidence") or {}

    ant_meta = metadata.get("antecedent") or {}
    cons_meta = metadata.get("consequent") or {}
    antecedent = ant_meta.get("full") if isinstance(ant_meta, dict) else ant_meta
    consequent = cons_meta.get("full") if isinstance(cons_meta, dict) else cons_meta

    if not antecedent:
        antecedent = metadata.get("antecedent") or "unknown"
    if not consequent:
        consequent = metadata.get("consequent") or "unknown"

    confidence = _as_float(
        evidence.get("confidence") if isinstance(evidence, dict) else None,
        0.0,
    )
    lift = _as_float(
        evidence.get("lift") if isinstance(evidence, dict) else None,
        0.0,
    )
    support = _as_float(
        evidence.get("support") if isinstance(evidence, dict) else None,
        0.0,
    )

    # Backward-compatibility for alternate evidence keys.
    if support <= 0 and isinstance(evidence, dict):
        support = _as_float(evidence.get("nAB"), 0.0)

    window_sec = _as_int(
        evidence.get("delta_window_sec") if isinstance(evidence, dict) else None,
        0,
    )
    score = round((confidence * max(lift, 1.0)) + support, 3)

    zone = (
        metadata.get("zone")
        or metadata.get("zone_filter")
        or metadata.get("room")
        or ""
    )

    return {
        "id": pattern.get("pattern_id"),
        "pattern_id": pattern.get("pattern_id"),
        "candidate_id": pattern.get("candidate_id"),
        "state": pattern.get("state"),
        "A": antecedent,
        "B": consequent,
        "antecedent": antecedent,
        "consequent": consequent,
        "confidence": round(confidence, 3),
        "lift": round(lift, 3),
        "support": round(support, 3),
        "score": score,
        "window_sec": window_sec,
        "zone": zone,
        "created_at": pattern.get("created_at"),
        "metadata": metadata,
        "evidence": evidence,
    }


def _collect_rules(limit: int, min_confidence: float = 0.0, zone: Optional[str] = None) -> List[Dict[str, Any]]:
    if not _habitus_service:
        return []

    raw_patterns = _habitus_service.list_recent_patterns(limit=max(limit * 3, limit))
    rules: List[Dict[str, Any]] = []
    for pattern in raw_patterns:
        rule = _normalize_rule_from_pattern(pattern)
        if rule["confidence"] < min_confidence:
            continue
        if zone and zone not in str(rule.get("zone") or ""):
            continue
        rules.append(rule)
        if len(rules) >= limit:
            break
    return rules


def init_habitus_api(service: HabitusService, brain_service: Optional[BrainGraphService] = None):
    """Initialize the habitus API with service instance."""
    global _habitus_service, _brain_graph_service
    _habitus_service = service
    _brain_graph_service = brain_service


@habitus_bp.route('/config', methods=['GET'])
@require_api_key
def get_config() -> Response:
    """Get persisted Habitus Miner configuration."""
    if not _habitus_service:
        return jsonify({"ok": False, "error": "Habitus service not initialized"}), 503
    return jsonify({"ok": True, "config": _habitus_service.get_config()})


@habitus_bp.route('/config', methods=['POST'])
@require_api_key
def set_config() -> Response:
    """Update persisted Habitus Miner configuration (partial merge)."""
    if not _habitus_service:
        return jsonify({"ok": False, "error": "Habitus service not initialized"}), 503
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400
    cfg = _habitus_service.set_config(body)
    return jsonify({"ok": True, "config": cfg})

@habitus_bp.route('/mine', methods=['POST'])
@require_api_key
def trigger_mining() -> Response:
    """
    Trigger habitus pattern mining and candidate creation.
    
    Optional JSON body:
    {
        "lookback_hours": 72,  // How far back to analyze (default 72)
        "force": false,        // Force run even if recent (default false)
        "zone": "kitchen"      // Zone ID to filter patterns (optional)
    }
    """
    if not _habitus_service:
        return jsonify({"error": "Habitus service not initialized"}), 503
        
    try:
        # Parse request parameters
        data = request.get_json() or {}
        lookback_hours = data.get("lookback_hours", 72)
        force = data.get("force", False)
        zone = data.get("zone")  # New: Zone filter parameter
        
        # Validate parameters
        if not isinstance(lookback_hours, int) or lookback_hours < 1 or lookback_hours > 168:
            return jsonify({"error": "lookback_hours must be between 1 and 168"}), 400
            
        if not isinstance(force, bool):
            return jsonify({"error": "force must be boolean"}), 400
            
        if zone is not None and not isinstance(zone, str):
            return jsonify({"error": "zone must be a string"}), 400
            
        if zone is not None and len(zone) > 100:
            return jsonify({"error": "zone must be less than 100 characters"}), 400
            
        logger.info(f"Mining request: lookback_hours={lookback_hours}, force={force}, zone={zone}")
        
        # Run mining
        results = _habitus_service.mine_and_create_candidates(lookback_hours, force, zone=zone)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Mining endpoint error: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@habitus_bp.route('/stats', methods=['GET'])
@require_api_key
def get_stats() -> Response:
    """Get habitus mining statistics and configuration."""
    if not _habitus_service:
        return jsonify({"error": "Habitus service not initialized"}), 503
        
    try:
        stats = _habitus_service.get_pattern_stats()
        
        # Add current timestamp
        stats["current_timestamp"] = int(time.time() * 1000)
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Stats endpoint error: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

@habitus_bp.route('/patterns', methods=['GET'])
@require_api_key  
def get_patterns() -> Response:
    """
    Get recently discovered patterns from candidates.
    
    Query parameters:
    - limit: Number of patterns to return (default 10, max 100)
    """
    if not _habitus_service:
        return jsonify({"error": "Habitus service not initialized"}), 503
        
    try:
        # Parse limit parameter
        limit = request.args.get('limit', '10')
        try:
            limit = int(limit)
            if limit < 1 or limit > 100:
                return jsonify({"error": "limit must be between 1 and 100"}), 400
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400
            
        patterns = _habitus_service.list_recent_patterns(limit)
        
        return jsonify({
            "version": 1,
            "timestamp": int(time.time() * 1000),
            "count": len(patterns),
            "patterns": patterns
        })
        
    except Exception as e:
        logger.error(f"Patterns endpoint error: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500


@habitus_bp.route('/rules', methods=['GET'])
@require_api_key
def get_rules() -> Response:
    """Compatibility endpoint: return discovered rules for dashboard/sensors."""
    if not _habitus_service:
        return jsonify({"status": "error", "message": "Habitus service not initialized"}), 503

    try:
        limit = max(1, min(int(request.args.get("limit", "50")), 500))
    except ValueError:
        return jsonify({"status": "error", "message": "limit must be an integer"}), 400

    min_confidence = _as_float(request.args.get("min_confidence"), 0.0)
    zone = request.args.get("zone")
    rules = _collect_rules(limit=limit, min_confidence=min_confidence, zone=zone)

    return jsonify(
        {
            "status": "ok",
            "timestamp": int(time.time() * 1000),
            "count": len(rules),
            "total_rules": len(rules),
            "rules": rules,
        }
    )


@habitus_bp.route('/rules/summary', methods=['GET'])
@require_api_key
def get_rules_summary() -> Response:
    """Compatibility endpoint for Habitus Miner summary sensors."""
    if not _habitus_service:
        return jsonify({"status": "error", "message": "Habitus service not initialized"}), 503

    rules = _collect_rules(limit=200)
    total_rules = len(rules)
    avg_confidence = round(sum(r["confidence"] for r in rules) / total_rules, 3) if total_rules else 0.0
    avg_lift = round(sum(r["lift"] for r in rules) / total_rules, 3) if total_rules else 0.0
    top_rules = sorted(rules, key=lambda r: r.get("score", 0.0), reverse=True)[:10]

    by_state: Dict[str, int] = {}
    domain_patterns: Dict[str, Dict[str, Any]] = {}
    for rule in rules:
        st = str(rule.get("state") or "unknown")
        by_state[st] = by_state.get(st, 0) + 1

        a_dom = str(rule.get("A", "")).split(":", 1)[0].split(".", 1)[0]
        b_dom = str(rule.get("B", "")).split(":", 1)[0].split(".", 1)[0]
        key = f"{a_dom}->{b_dom}"
        item = domain_patterns.setdefault(key, {"count": 0})
        item["count"] += 1

    stats = _habitus_service.get_pattern_stats()
    last_run_sec = _as_int(stats.get("last_mining_run"), 0)
    last_mining_ts = (last_run_sec * 1000) if last_run_sec > 0 else None

    return jsonify(
        {
            "status": "ok",
            "total_rules": total_rules,
            "avg_confidence": avg_confidence,
            "avg_lift": avg_lift,
            "rules_by_state": by_state,
            "top_rules": top_rules,
            "domain_patterns": domain_patterns,
            "storage_stats": {
                "total_events_processed": _as_int(stats.get("graph_edges"), 0),
                "last_mining_ts": last_mining_ts,
                "files_exist": {
                    "rules": total_rules > 0,
                    "events_cache": _as_int(stats.get("graph_edges"), 0) > 0,
                },
            },
        }
    )


@habitus_bp.route('/status', methods=['GET'])
@require_api_key
def get_status() -> Response:
    """Compatibility endpoint expected by HA Habitus Miner sensors."""
    if not _habitus_service:
        return jsonify({"status": "error", "message": "Habitus service not initialized"}), 503

    stats = _habitus_service.get_pattern_stats()
    total_rules = len(_collect_rules(limit=200))
    last_run_sec = _as_int(stats.get("last_mining_run"), 0)

    return jsonify(
        {
            "status": "ok",
            "version": "compat-v1",
            "statistics": {
                "total_rules": total_rules,
                "total_events_processed": _as_int(stats.get("graph_edges"), 0),
                "last_mining_ts": (last_run_sec * 1000) if last_run_sec > 0 else None,
                "files_exist": {
                    "rules": total_rules > 0,
                    "events_cache": _as_int(stats.get("graph_edges"), 0) > 0,
                },
            },
            "config": {
                **(stats.get("mining_config") or {}),
                "max_rules": 200,
            },
        }
    )


@habitus_bp.route('/dashboard_cards/rules', methods=['GET'])
@require_api_key
def get_dashboard_card_rules() -> Response:
    """Compatibility endpoint used by HA coordinator suggestion widgets."""
    min_confidence = _as_float(request.args.get("min_confidence"), 0.7)
    limit = max(1, min(_as_int(request.args.get("limit"), 10), 100))
    zone = request.args.get("zone")
    rules = _collect_rules(limit=limit, min_confidence=min_confidence, zone=zone)

    cards = [
        {
            "type": "rule",
            "title": f"{r.get('A', '?')} -> {r.get('B', '?')}",
            "confidence": r.get("confidence", 0.0),
            "lift": r.get("lift", 0.0),
            "zone": r.get("zone", ""),
        }
        for r in rules
    ]

    return jsonify(
        {
            "ok": True,
            "count": len(rules),
            "rules": rules,
            "cards": cards,
            "config": {
                "min_confidence": min_confidence,
                "limit": limit,
                "zone": zone,
            },
        }
    )

@habitus_bp.route('/health', methods=['GET'])
@require_api_key
def health_check() -> Response:
    """Health check for habitus service."""
    if not _habitus_service:
        return jsonify({"status": "error", "message": "Service not initialized"}), 503
        
    try:
        # Basic health check - verify service is responsive
        stats = _habitus_service.get_pattern_stats()
        
        return jsonify({
            "status": "ok",
            "timestamp": int(time.time() * 1000),
            "mining_enabled": True,
            "last_run_ago_seconds": int(time.time() - _habitus_service.last_mining_run) if _habitus_service.last_mining_run > 0 else None
        })
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "error", 
            "message": f"Service error: {str(e)}"
        }), 500

@habitus_bp.route('/zones', methods=['GET'])
@require_api_key
def get_zones() -> Response:
    """
    Get available zones for zone-filtered pattern mining.
    
    Returns a list of zones discovered in the brain graph.
    These zones can be used with the /mine endpoint's zone parameter.
    """
    if not _brain_graph_service:
        return jsonify({"error": "Brain graph service not initialized"}), 503
        
    try:
        zones = _brain_graph_service.get_zones()
        
        return jsonify({
            "version": 1,
            "timestamp": int(time.time() * 1000),
            "count": len(zones),
            "zones": zones
        })
        
    except Exception as e:
        logger.error(f"Zones endpoint error: {e}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500
