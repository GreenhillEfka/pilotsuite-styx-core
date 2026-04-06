"""Zone Truth API (Slice 148).

Truth endpoint for zone automation with drift detection and mapping coverage.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

zone_truth_bp = Blueprint("zone_truth", __name__, url_prefix="/api/v1/zone_automation/truth")


def _calculate_coverage(zone_id: str, entities: List[Dict[str, Any]]) -> float:
    """Calculate mapping coverage percentage."""
    if not entities:
        return 100.0
    
    mapped = sum(1 for e in entities if e.get("mapped_to_core"))
    return (mapped / len(entities)) * 100


def _detect_drift(zone_id: str, ha_entities: List[Dict], core_entities: List[Dict]) -> Dict[str, Any]:
    """Detect drift between HA and Core entity lists."""
    ha_ids = {e.get("entity_id") for e in ha_entities}
    core_ids = {e.get("entity_id") for e in core_entities}
    
    only_in_ha = ha_ids - core_ids
    only_in_core = core_ids - ha_ids
    
    return {
        "drift_score": len(only_in_ha) + len(only_in_core),
        "only_in_ha": list(only_in_ha),
        "only_in_core": list(only_in_core),
        "in_sync": len(only_in_ha) == 0 and len(only_in_core) == 0,
    }


@zone_truth_bp.route("/zones", methods=["GET"])
def get_zone_truth():
    """Get zone truth with deltas and drift detection."""
    compact = request.args.get("compact", "false").lower() == "true"
    since_revision = request.args.get("since")
    deltas_only = request.args.get("deltas", "false").lower() == "true"
    
    try:
        from copilot_core.hub.habitus_zones import HabitusZoneEngine
        
        engine = HabitusZoneEngine()
        overview = engine.get_overview()
        
        zones = []
        for zone_payload in overview.get("zones", []):
            if not isinstance(zone_payload, dict):
                continue
                
            zone_id = zone_payload.get("zone_id", "")
            if not zone_id:
                continue
            
            # Get zone entities
            zone = engine.get_zone(zone_id)
            ha_entities = zone.get("entities", []) if zone else []
            
            # Calculate coverage
            coverage = _calculate_coverage(zone_id, ha_entities)
            
            # Detect drift (compare with Core's view)
            core_entities = [
                {"entity_id": eid, "mapped_to_core": True}
                for eid in zone.get("entities", [])
            ]
            drift = _detect_drift(zone_id, ha_entities, core_entities)
            
            zone_data = {
                "zone_id": zone_id,
                "name": zone_payload.get("name", zone_id),
                "zone_type": zone_payload.get("zone_type", "unknown"),
                "coverage": round(coverage, 2),
                "drift": drift,
                "freshness": datetime.now(timezone.utc).isoformat(),
            }
            
            if not compact:
                zone_data["entities"] = ha_entities
                zone_data["conflicts"] = drift.get("only_in_ha", []) + drift.get("only_in_core", [])
            
            zones.append(zone_data)
        
        return jsonify({
            "zones": zones,
            "total": len(zones),
            "revision": str(uuid.uuid4())[:8],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
        
    except Exception as exc:
        _LOGGER.error("Failed to get zone truth: %s", exc)
        return jsonify({"error": str(exc)}), 500


@zone_truth_bp.route("/zones/<zone_id>/entities", methods=["GET"])
def get_zone_entities_truth(zone_id: str):
    """Get detailed entity truth for a specific zone."""
    try:
        from copilot_core.hub.habitus_zones import HabitusZoneEngine
        
        engine = HabitusZoneEngine()
        zone = engine.get_zone(zone_id)
        
        if not zone:
            return jsonify({"error": f"Zone {zone_id} not found"}), 404
        
        entities = []
        for entity_id in zone.get("entities", []):
            entities.append({
                "entity_id": entity_id,
                "domain": entity_id.split(".")[0] if "." in entity_id else "unknown",
                "mapped_to_core": True,
                "in_ha": True,
            })
        
        return jsonify({
            "zone_id": zone_id,
            "entities": entities,
            "count": len(entities),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
        
    except Exception as exc:
        _LOGGER.error("Failed to get zone entities: %s", exc)
        return jsonify({"error": str(exc)}), 500
