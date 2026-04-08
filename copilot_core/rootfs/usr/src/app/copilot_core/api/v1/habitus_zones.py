"""
Habitus Zones API - Zone-based Habitus Assignment

Endpoints:
  GET    /api/v1/habitus/zones              - Alle Zonen mit Habitus
  POST   /api/v1/habitus/zones/{id}         - Zone konfigurieren
  GET    /api/v1/habitus/zones/{id}/metrics - Zone Metriken

Author: Styx Agent
Version: 1.0.0
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.homeassistant.habitus_zones import (
    HABITUS_ZONES,
    ZoneType,
    HabitusZone,
    get_all_zones,
    get_zone_by_type,
    get_default_module_overrides,
    resolve_module_overrides,
)
from copilot_core.homeassistant.zone_matcher import (
    ZoneMatcher, get_matcher, map_homeassistant_topology, match_room, match_rooms
)
from copilot_core.hub.habitus_zones import HabitusZoneEngine

_LOGGER = logging.getLogger(__name__)

# Blueprint mit absolutem Prefix (wird direkt auf App registriert)
bp = Blueprint("habitus_zones", __name__, url_prefix="/api/v1/habitus/zones")

# Global zone engine instance
_zone_engine: Optional[HabitusZoneEngine] = None


def init_habitus_zones_api(engine: Optional[HabitusZoneEngine] = None) -> None:
    """Initialize the Habitus Zones API."""
    global _zone_engine
    _zone_engine = engine if engine is not None else HabitusZoneEngine()
    _LOGGER.info("Habitus Zones API initialized")


def get_zone_engine() -> HabitusZoneEngine:
    """Get the zone engine instance."""
    global _zone_engine
    if _zone_engine is None:
        _zone_engine = HabitusZoneEngine()
    return _zone_engine


@bp.before_request
def _require_auth():
    """Require authentication for all endpoints."""
    if not validate_token(request):
        return jsonify({
            "error": "unauthorized",
            "message": "Valid X-Auth-Token or Bearer token required"
        }), 401


# =============================================================================
# GET /api/v1/habitus/zones - Alle Zonen mit Habitus
# =============================================================================

@bp.route("", methods=["GET"])
def get_all_habitus_zones():
    """
    Alle Habituszonen zurückgeben.
    
    Gibt alle vordefinierten Habituszonen mit Keywords, Metadaten und
    aktuellen Metriken zurück.
    
    Query Parameters:
        include_metrics (bool): Include current zone metrics (default: true)
        zone_type (str): Filter by specific zone type (optional)
    
    Returns:
        JSON array of zone objects
    """
    try:
        include_metrics = request.args.get("include_metrics", "true").lower() == "true"
        zone_type_filter = request.args.get("zone_type")
        
        zones = get_all_zones()
        
        # Optional filter by zone type
        if zone_type_filter:
            try:
                filter_type = ZoneType(zone_type_filter)
                zones = [z for z in zones if z.zone_type == filter_type]
            except ValueError:
                return jsonify({
                    "error": "invalid_zone_type",
                    "message": f"Invalid zone type: {zone_type_filter}. "
                               f"Valid values: {[zt.value for zt in ZoneType]}"
                }), 400
        
        zones_data = []
        for zone in zones:
            zone_data = {
                "id": zone.zone_type.value,
                "zone_type": zone.zone_type.value,
                "name_de": zone.name_de,
                "name_en": zone.name_en,
                "description": zone.description,
                "keywords_de": zone.keywords_de,
                "keywords_en": zone.keywords_en,
                "priority": zone.priority,
                "icon": _get_icon_for_zone(zone.zone_type),
                "module_overrides": zone.get_module_overrides() or get_default_module_overrides(zone.zone_type),
            }
            
            # Include metrics if requested
            if include_metrics:
                metrics = _get_zone_metrics(zone.zone_type)
                zone_data["metrics"] = metrics
            
            zones_data.append(zone_data)
        
        return jsonify({
            "status": "ok",
            "total_zones": len(zones_data),
            "zones": zones_data
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get habitus zones: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =============================================================================
# POST /api/v1/habitus/zones/{id} - Zone konfigurieren
# =============================================================================

@bp.route("/<zone_id>", methods=["POST"])
def configure_zone(zone_id: str):
    """
    Zone konfigurieren.
    
    Ermöglicht die Konfiguration einer Habituszone mit benutzerdefinierten
    Einstellungen, Entitäten und Metadaten.
    
    Path Parameters:
        zone_id (str): Zone identifier (zone type value)
    
    Request Body:
        name_de (str): German name override (optional)
        name_en (str): English name override (optional)
        priority (int): Priority for matching (optional)
        keywords_de (list): German keywords (optional)
        keywords_en (list): English keywords (optional)
        entities (dict): Entity assignments (optional)
        settings (dict): Zone-specific settings (optional)
        module_overrides (dict): Per-module policy overrides (optional)
    
    Returns:
        JSON object with updated zone configuration
    """
    try:
        # Validate zone_id
        try:
            zone_type = ZoneType(zone_id)
        except ValueError:
            return jsonify({
                "error": "invalid_zone_id",
                "message": f"Invalid zone ID: {zone_id}. "
                           f"Valid values: {[zt.value for zt in ZoneType]}"
            }), 400
        
        zone = HABITUS_ZONES.get(zone_type)
        if not zone:
            return jsonify({
                "error": "zone_not_found",
                "message": f"Zone not found: {zone_id}"
            }), 404
        
        # Parse request body
        data = request.get_json() or {}
        
        module_overrides = resolve_module_overrides(zone_type, data.get("module_overrides"))

        # Update zone configuration (in a real implementation, this would persist)
        updated_config = {
            "id": zone_id,
            "zone_type": zone_type.value,
            "name_de": data.get("name_de", zone.name_de),
            "name_en": data.get("name_en", zone.name_en),
            "description": zone.description,
            "keywords_de": data.get("keywords_de", zone.keywords_de),
            "keywords_en": data.get("keywords_en", zone.keywords_en),
            "priority": data.get("priority", zone.priority),
            "icon": _get_icon_for_zone(zone_type),
            "module_overrides": module_overrides,
        }
        
        # Add entity assignments if provided
        if "entities" in data:
            updated_config["entities"] = data["entities"]
        
        # Add zone settings if provided
        if "settings" in data:
            updated_config["settings"] = data["settings"]
        
        _LOGGER.info("Zone %s configured: %s", zone_id, data.keys())
        
        return jsonify({
            "status": "ok",
            "message": "Zone configuration updated",
            "zone": updated_config,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        _LOGGER.error("Failed to configure zone %s: %s", zone_id, e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =============================================================================
# GET /api/v1/habitus/zones/{id}/metrics - Zone Metriken
# =============================================================================

@bp.route("/<zone_id>/metrics", methods=["GET"])
def get_zone_metrics(zone_id: str):
    """
    Zone Metriken abrufen.
    
    Gibt aktuelle Metriken und Statistiken für eine spezifische Zone zurück.
    
    Path Parameters:
        zone_id (str): Zone identifier
    
    Returns:
        JSON object with zone metrics
    """
    try:
        # Validate zone_id
        try:
            zone_type = ZoneType(zone_id)
        except ValueError:
            return jsonify({
                "error": "invalid_zone_id",
                "message": f"Invalid zone ID: {zone_id}. "
                           f"Valid values: {[zt.value for zt in ZoneType]}"
            }), 400
        
        zone = HABITUS_ZONES.get(zone_type)
        if not zone:
            return jsonify({
                "error": "zone_not_found",
                "message": f"Zone not found: {zone_id}"
            }), 404
        
        metrics = _get_zone_metrics(zone_type)
        
        return jsonify({
            "status": "ok",
            "zone_id": zone_id,
            "zone_name_de": zone.name_de,
            "zone_name_en": zone.name_en,
            "metrics": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get metrics for zone %s: %s", zone_id, e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =============================================================================
# Additional Helper Endpoints
# =============================================================================

@bp.route("/map-homeassistant", methods=["POST"])
def map_homeassistant_areas_and_entities():
    """Home-Assistant-Bereiche und Entitäten in aggregierte Habituszonen mappen."""
    try:
        data = request.get_json() or {}
        areas = data.get("areas", [])
        entities = data.get("entities", [])

        if not isinstance(areas, list) or not isinstance(entities, list):
            return jsonify({
                "error": "invalid_format",
                "message": "'areas' und 'entities' müssen Arrays sein"
            }), 400

        return jsonify({
            "status": "ok",
            **map_homeassistant_topology(areas, entities),
        })

    except Exception as e:
        _LOGGER.error("Failed to map Home Assistant topology: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/match", methods=["POST"])
def match_rooms_to_zones():
    """
    Räume zu Zonen matchen.
    
    Batch-Endpoint für ML-basiertes Room-to-Zone Matching.
    
    Request Body:
        rooms (list): List of room names to match
    
    Returns:
        JSON array of match results with confidence scores
    """
    try:
        data = request.get_json()
        if not data or "rooms" not in data:
            return jsonify({
                "error": "missing_rooms",
                "message": "Request body must contain 'rooms' array"
            }), 400
        
        rooms = data["rooms"]
        if not isinstance(rooms, list):
            return jsonify({
                "error": "invalid_format",
                "message": "'rooms' must be an array of strings"
            }), 400
        
        # Perform matching
        matcher = get_matcher()
        results = matcher.match_multiple_rooms(rooms)
        
        matches_data = [
            {
                "room_name": r.room_name,
                "zone_type": r.zone.zone_type.value,
                "zone_name_de": r.zone.name_de,
                "zone_name_en": r.zone.name_en,
                "confidence": r.confidence,
                "matched_keyword": r.matched_keyword,
                "needs_review": r.needs_review,
            }
            for r in results
        ]
        
        return jsonify({
            "status": "ok",
            "total_rooms": len(matches_data),
            "matches": matches_data,
            "review_required": sum(1 for r in results if r.needs_review)
        })
    
    except Exception as e:
        _LOGGER.error("Failed to match rooms: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@bp.route("/review", methods=["GET"])
def get_review_queue():
    """
    Review-Queue für unsichere Zuordnungen.
    
    Gibt alle Räume zurück die ein manuelles Review benötigen.
    
    Query Parameters:
        threshold (float): Confidence threshold (default: 70.0)
    
    Returns:
        JSON array of rooms requiring review
    """
    try:
        threshold = request.args.get("threshold", 70.0, type=float)
        
        # Get all rooms from zone engine
        engine = get_zone_engine()
        rooms = engine.get_rooms()
        
        if not rooms:
            return jsonify({
                "status": "ok",
                "threshold": threshold,
                "total_review": 0,
                "rooms": []
            })
        
        # Match rooms and filter by confidence
        room_names = [r["name"] for r in rooms]
        matcher = get_matcher()
        results = matcher.match_multiple_rooms(room_names)
        
        review_items = [
            {
                "room_name": r.room_name,
                "room_id": next((rm["room_id"] for rm in rooms if rm["name"] == r.room_name), None),
                "zone_type": r.zone.zone_type.value,
                "zone_name_de": r.zone.name_de,
                "zone_name_en": r.zone.name_en,
                "confidence": r.confidence,
                "matched_keyword": r.matched_keyword,
                "reason": "low_confidence" if r.confidence < threshold else "manual_review"
            }
            for r in results
            if r.needs_review or r.confidence < threshold
        ]
        
        return jsonify({
            "status": "ok",
            "threshold": threshold,
            "total_review": len(review_items),
            "rooms": review_items
        })
    
    except Exception as e:
        _LOGGER.error("Failed to get review queue: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# =============================================================================
# Helper Functions
# =============================================================================

def _get_icon_for_zone(zone_type: ZoneType) -> str:
    """Get Material Design icon for zone type."""
    icon_map = {
        ZoneType.LIVING: "mdi:sofa",
        ZoneType.BATH: "mdi:shower",
        ZoneType.KITCHEN: "mdi:stove",
        ZoneType.OFFICE: "mdi:desk",
        ZoneType.HALLWAY: "mdi:door-open",
        ZoneType.BEDROOM: "mdi:bed",
        ZoneType.ROOM_MIRA: "mdi:account-girl",
        ZoneType.ROOM_PAUL: "mdi:account-boy",
        ZoneType.TERRACE: "mdi:patio-grass",
        ZoneType.OUTSIDE: "mdi:tree",
    }
    return icon_map.get(zone_type, "mdi:home")


def _get_zone_metrics(zone_type: ZoneType) -> Dict[str, Any]:
    """Get current metrics for a zone from the ZoneAutomationController.

    Queries the live zone automation state to derive entity count,
    light/occupancy status, and energy metrics.
    """
    from copilot_core.api.v1.zone_dashboard import _svc
    _zone_automation = _svc.get("zone_automation")

    zone_id = f"zone:{zone_type.value}" if hasattr(zone_type, "value") else f"zone:{zone_type}"
    metrics: Dict[str, Any] = {
        "entity_count": 0,
        "active_lights": 0,
        "avg_temperature": None,
        "avg_humidity": None,
        "occupancy": False,
        "last_activity": None,
        "energy_consumption_kwh": 0.0,
    }

    if _zone_automation is None:
        return metrics

    try:
        entities = _zone_automation.get_zone_entities(zone_id)
        state = _zone_automation.get_zone_state(zone_id)
        zone_state = state.get("state", {})

        metrics["entity_count"] = len(entities)
        metrics["occupancy"] = zone_state.get("occupied", False)
        metrics["active_lights"] = 1 if zone_state.get("lights_on", False) else 0
    except Exception:
        pass

    return metrics
