"""Zone Truth API (Slice 148).

<<<<<<< HEAD
Provides ground truth for zone automation with drift detection and coverage metrics.
=======
Truth endpoint for zone automation with drift detection and mapping coverage.
>>>>>>> v1.0.0-rc2
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

zone_truth_bp = Blueprint("zone_truth", __name__, url_prefix="/api/v1/zone_automation/truth")

<<<<<<< HEAD
=======

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


>>>>>>> v1.0.0-rc2
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
            
<<<<<<< HEAD
=======
            # Get zone entities
>>>>>>> v1.0.0-rc2
            zone = engine.get_zone(zone_id)
            ha_entities = zone.get("entities", []) if zone else []
            
            # Calculate coverage
<<<<<<< HEAD
            total = len(ha_entities)
            mapped = sum(1 for e in ha_entities if isinstance(e, dict) and e.get("mapped_to_core"))
            coverage = (mapped / total * 100) if total > 0 else 100.0
=======
            coverage = _calculate_coverage(zone_id, ha_entities)
            
            # Detect drift (compare with Core's view)
            core_entities = [
                {"entity_id": eid, "mapped_to_core": True}
                for eid in zone.get("entities", [])
            ]
            drift = _detect_drift(zone_id, ha_entities, core_entities)
>>>>>>> v1.0.0-rc2
            
            zone_data = {
                "zone_id": zone_id,
                "name": zone_payload.get("name", zone_id),
                "zone_type": zone_payload.get("zone_type", "unknown"),
                "coverage": round(coverage, 2),
<<<<<<< HEAD
                "drift": {"score": 0, "in_sync": True}, # Placeholder
=======
                "drift": drift,
>>>>>>> v1.0.0-rc2
                "freshness": datetime.now(timezone.utc).isoformat(),
            }
            
            if not compact:
                zone_data["entities"] = ha_entities
<<<<<<< HEAD
                zone_data["conflicts"] = []
=======
                zone_data["conflicts"] = drift.get("only_in_ha", []) + drift.get("only_in_core", [])
>>>>>>> v1.0.0-rc2
            
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
        
<<<<<<< HEAD
        entities = [
            {
                "entity_id": eid,
                "domain": eid.split(".")[0] if "." in eid else "unknown",
                "mapped_to_core": True,
                "in_ha": True,
            }
            for eid in zone.get("entities", [])
        ]
=======
        entities = []
        for entity_id in zone.get("entities", []):
            entities.append({
                "entity_id": entity_id,
                "domain": entity_id.split(".")[0] if "." in entity_id else "unknown",
                "mapped_to_core": True,
                "in_ha": True,
            })
>>>>>>> v1.0.0-rc2
        
        return jsonify({
            "zone_id": zone_id,
            "entities": entities,
            "count": len(entities),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
        
    except Exception as exc:
        _LOGGER.error("Failed to get zone entities: %s", exc)
        return jsonify({"error": str(exc)}), 500
