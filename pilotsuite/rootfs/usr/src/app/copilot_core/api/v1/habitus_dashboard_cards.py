"""
habitus_dashboard_cards API endpoint (v0.2)

Provides dashboard pattern recommendations and templates for Home Assistant Lovelace.
Features:
- Zone-aware patterns from Habitus Miner
- Dynamic card generation based on discovered rules
- Real-time integration with Brain Graph
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
import logging

_LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_brain_graph_service():
    """Get Brain Graph service instance."""
    try:
        from copilot_core.brain_graph.provider import get_graph_service
        return get_graph_service()
    except Exception as e:
        _LOGGER.warning("Brain Graph service not available: %s", e)
        return None


def _get_habitus_service():
    """Get Habitus Miner service instance."""
    try:
        from copilot_core.habitus.provider import get_habitus_service
        return get_habitus_service()
    except Exception as e:
        _LOGGER.warning("Habitus service not available: %s", e)
        return None


bp = Blueprint("habitus_dashboard_cards", __name__, url_prefix="/habitus/dashboard_cards")

from copilot_core.api.security import validate_token as _validate_token


@bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


@bp.get("")
def get_dashboard_patterns():
    """
    Return recommended dashboard patterns and card templates.
    
    Query params:
    - type: "overview" | "room" | "energy" | "sleep" | "zone" (default: all)
    - format: "yaml" | "json" (default: json)
    - zone: zone_id for zone-specific patterns (e.g., "kitchen", "zone:living_room")
    """
    pattern_type = request.args.get("type", "all").lower()
    output_format = request.args.get("format", "json").lower()
    zone_id = request.args.get("zone")

    patterns = _get_patterns(pattern_type, zone_id)

    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "type": pattern_type,
        "zone": zone_id,
        "format": output_format,
        "patterns": patterns,
        "documentation": "/docs/module_specs/habitus_dashboard_cards_v0.2.md"
    })


@bp.get("/zones")
def get_zones():
    """Get list of available zones for dashboard generation from Brain Graph."""
    brain_service = _get_brain_graph_service()
    
    if not brain_service:
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "zones": [],
            "error": "Brain Graph service not available"
        })
    
    try:
        zones = brain_service.get_zones()
        return jsonify({
            "ok": True,
            "time": _now_iso(),
            "zones": zones,
            "source": "brain_graph"
        })
    except Exception as e:
        _LOGGER.error("Failed to get zones: %s", e)
        return jsonify({
            "ok": False,
            "error": str(e),
            "zones": []
        }), 500


@bp.get("/zone/<zone_id>")
def get_zone_patterns(zone_id):
    """
    Get zone-specific patterns and dashboard templates.
    
    Path params:
    - zone_id: Zone identifier (e.g., "kitchen" or "zone:kitchen")
    """
    # Normalize zone_id
    if not zone_id.startswith("zone:"):
        zone_id = f"zone:{zone_id}"
    
    brain_service = _get_brain_graph_service()
    zone_entities = []
    
    if brain_service:
        try:
            zone_data = brain_service.get_zone_entities(zone_id)
            zone_entities = zone_data.get("entities", [])
        except Exception as e:
            _LOGGER.warning("Failed to get zone entities: %s", e)
    
    patterns = _get_patterns("zone", zone_id)
    
    # Add zone entity data to patterns
    if zone_entities:
        patterns["zone_data"] = {
            "zone_id": zone_id,
            "entity_count": len(zone_entities),
            "entities": zone_entities[:20]  # Limit for response
        }
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "zone_id": zone_id,
        "patterns": patterns
    })


@bp.get("/rules")
def get_rule_cards():
    """
    Generate dashboard cards from discovered A→B rules.
    
    Query params:
    - min_confidence: Minimum confidence threshold (default: 0.7)
    - limit: Maximum number of rules to include (default: 10)
    - zone: Filter by zone (optional)
    """
    min_confidence = request.args.get("min_confidence", 0.7, type=float)
    limit = request.args.get("limit", 10, type=int)
    zone = request.args.get("zone")
    
    habitus_service = _get_habitus_service()
    rules_data = []
    
    if habitus_service:
        try:
            # Get rules from Habitus Miner
            rules = habitus_service.get_rules(
                limit=limit,
                min_score=min_confidence,
                zone_filter=zone
            )
            rules_data = [
                {
                    "A": rule.A,
                    "B": rule.B,
                    "confidence": round(rule.confidence, 3),
                    "lift": round(rule.lift, 2),
                    "nAB": rule.nAB,
                }
                for rule in rules[:limit]
            ]
        except Exception as e:
            _LOGGER.warning("Failed to get habitus rules: %s", e)
    
    cards = _generate_rule_cards(min_confidence, limit, zone, rules_data)
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "cards": cards,
        "rules": rules_data,
        "config": {
            "min_confidence": min_confidence,
            "limit": limit,
            "zone": zone
        }
    })


def _get_patterns(pattern_type: str, zone_id: str = None) -> dict:
    """Return pattern templates based on type and zone."""
    
    base_patterns = {
        "principles": {
            "hierarchy": "Overview → Diagnosis → Detail",
            "time_windows": ["24h (operational)", "7 days (trend)", "30 days (seasonality)"],
            "max_lines_per_graph": 3,
            "title_convention": "Always include time window, e.g. '(24h)'",
            "zone_aware": True
        },
        "recommended_cards": {
            "status": ["tile", "entities", "glance"],
            "trends": ["history-graph", "statistics-graph"],
            "events": ["logbook"],
            "layout": ["grid", "vertical-stack", "horizontal-stack"],
            "habitus": ["custom:habitus-zone-card", "custom:habitus-rules-card"]
        }
    }

    templates = {}

    if pattern_type in ("all", "overview"):
        templates["overview"] = {
            "description": "Main overview page with tiles + drill-down",
            "example": {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    {
                        "type": "tile",
                        "entity": "sensor.room_temperature",
                        "name": "Temperature",
                        "state_content": ["state", "last_changed"],
                        "tap_action": {
                            "action": "navigate",
                            "navigation_path": "/dashboard-habitus/room-detail"
                        }
                    },
                    {
                        "type": "custom:habitus-zone-card",
                        "zone": "zone:kitchen",
                        "show_rules": True
                    }
                ]
            }
        }

    if pattern_type in ("all", "room"):
        templates["room_detail"] = {
            "description": "Room detail page: status + short-term + long-term trends + events",
            "sections": [
                {
                    "purpose": "Current status",
                    "card_type": "entities",
                    "entities": ["temperature", "humidity", "co2", "window_status"]
                },
                {
                    "purpose": "Short-term trend (24h)",
                    "card_type": "history-graph",
                    "hours_to_show": 24,
                    "entities": ["temperature", "humidity"]
                },
                {
                    "purpose": "Long-term aggregated trend (7 days)",
                    "card_type": "statistics-graph",
                    "period": "day",
                    "days_to_show": 7,
                    "stat_types": ["mean", "min", "max"],
                    "entities": ["temperature"]
                },
                {
                    "purpose": "Events (24h)",
                    "card_type": "logbook",
                    "hours_to_show": 24,
                    "entities": ["binary_sensor.motion", "binary_sensor.door"]
                },
                {
                    "purpose": "Habitus patterns",
                    "card_type": "custom:habitus-rules-card",
                    "config": {
                        "zone": zone_id,
                        "min_confidence": 0.7
                    }
                }
            ]
        }

    if pattern_type in ("all", "energy"):
        templates["energy"] = {
            "description": "Energy consumption patterns",
            "example": {
                "type": "vertical-stack",
                "cards": [
                    {
                        "type": "tile",
                        "entity": "sensor.power_consumption",
                        "name": "Current Power (W)"
                    },
                    {
                        "type": "statistics-graph",
                        "title": "Daily Energy (7 days)",
                        "period": "day",
                        "days_to_show": 7,
                        "stat_types": ["sum"],
                        "entities": ["sensor.energy_kwh"]
                    },
                    {
                        "type": "custom:habitus-rules-card",
                        "config": {
                            "domain": "energy",
                            "show_suggestions": True
                        }
                    }
                ]
            }
        }

    if pattern_type in ("all", "sleep"):
        templates["sleep"] = {
            "description": "Sleep/rest patterns",
            "example": {
                "type": "vertical-stack",
                "cards": [
                    {
                        "type": "tile",
                        "entity": "sensor.sleep_duration_last_night",
                        "name": "Last Night Sleep"
                    },
                    {
                        "type": "statistics-graph",
                        "title": "Sleep Duration - Weekly Mean",
                        "period": "week",
                        "stat_types": ["mean"],
                        "entities": ["sensor.sleep_duration"]
                    }
                ]
            }
        }

    if pattern_type in ("all", "zone") and zone_id:
        templates["zone_specific"] = {
            "description": f"Zone-specific patterns for {zone_id}",
            "zone_id": zone_id,
            "cards": [
                {
                    "type": "custom:habitus-zone-card",
                    "zone": zone_id,
                    "show_rules": True,
                    "show_trends": True,
                    "time_window": "24h"
                },
                {
                    "type": "history-graph",
                    "title": f"{zone_id.replace('zone:', '').replace('_', ' ').title()} Activity (24h)",
                    "hours_to_show": 24,
                    "entities": []  # To be filled with zone entities
                }
            ],
            "note": "Entities populated from Brain Graph zone query"
        }

    return {
        "base": base_patterns,
        "templates": templates
    }


def _generate_rule_cards(min_confidence: float, limit: int, zone: str = None, rules_data: list = None) -> list:
    """Generate dashboard cards from discovered A→B rules."""
    
    cards = []
    rules_data = rules_data or []
    
    # If we have real rules, generate cards from them
    if rules_data:
        for rule in rules_data:
            rule_card = {
                "type": "custom:habitus-rule-card",
                "title": f"Pattern: {rule['A']} → {rule['B']}",
                "config": {
                    "antecedent": rule["A"],
                    "consequent": rule["B"],
                    "confidence": rule["confidence"],
                    "lift": rule["lift"],
                    "occurrences": rule["nAB"],
                    "zone": zone,
                    "show_create_automation": rule["confidence"] >= 0.8
                }
            }
            cards.append(rule_card)
    
    # Template for summary card
    if cards:
        summary_card = {
            "type": "custom:habitus-summary-card",
            "title": f"Discovered Patterns ({len(cards)})",
            "config": {
                "zone": zone,
                "min_confidence": min_confidence,
                "total_rules": len(rules_data)
            }
        }
        cards.insert(0, summary_card)
    else:
        # No rules found, return placeholder templates
        cards.append({
            "type": "custom:habitus-placeholder-card",
            "title": "No Patterns Yet",
            "config": {
                "message": "Collect more events to discover patterns",
                "min_confidence": min_confidence
            }
        })
    
    return cards


@bp.get("/health")
def health():
    """Health check for dashboard_cards module."""
    brain_ok = _get_brain_graph_service() is not None
    habitus_ok = _get_habitus_service() is not None
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "module": "habitus_dashboard_cards",
        "version": "0.2.0",
        "features": [
            "zone_aware_patterns",
            "rule_based_cards",
            "dynamic_templates",
            "brain_graph_integration",
            "habitus_miner_integration"
        ],
        "integrations": {
            "brain_graph": "ok" if brain_ok else "unavailable",
            "habitus_miner": "ok" if habitus_ok else "unavailable"
        },
        "status": "active"
    })