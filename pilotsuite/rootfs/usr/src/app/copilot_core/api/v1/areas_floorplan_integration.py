"""Areas/Floorplan Integration (Slice 174).

Cross-reference linking between Areas and Floorplans.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)
areas_floorplan_bp = Blueprint("areas_floorplan", __name__, url_prefix="/api/v1/areas")

# Cross-reference mappings (in-memory, replace with DB)
_area_floorplan_map: Dict[str, str] = {}  # area_id -> floorplan_id
_floorplan_area_map: Dict[str, List[str]] = {}  # floorplan_id -> [area_ids]

@areas_floorplan_bp.route("/<area_id>/floorplan", methods=["GET"])
def get_area_floorplan(area_id: str):
    """Returns the floorplan assigned to an area."""
    floorplan_id = _area_floorplan_map.get(area_id)
    if not floorplan_id:
        return jsonify({"error": "No floorplan assigned to area"}), 404
    
    return jsonify({
        "area_id": area_id,
        "floorplan_id": floorplan_id,
        "zones": _get_zones_for_floorplan(floorplan_id)
    })

@areas_floorplan_bp.route("/<area_id>/floorplan", methods=["PUT"])
def set_area_floorplan(area_id: str):
    """Assigns a floorplan to an area."""
    data = request.get_json() or {}
    floorplan_id = data.get("floorplan_id")
    
    if not floorplan_id:
        return jsonify({"error": "floorplan_id required"}), 400
    
    # Update mappings
    _area_floorplan_map[area_id] = floorplan_id
    if floorplan_id not in _floorplan_area_map:
        _floorplan_area_map[floorplan_id] = []
    if area_id not in _floorplan_area_map[floorplan_id]:
        _floorplan_area_map[floorplan_id].append(area_id)
    
    return jsonify({"status": "assigned", "area_id": area_id, "floorplan_id": floorplan_id})

@areas_floorplan_bp.route("/floorplan/<floorplan_id>/zones/resolve", methods=["GET"])
def resolve_floorplan_zones(floorplan_id: str):
    """Resolves floorplan zones to their corresponding areas."""
    area_ids = _floorplan_area_map.get(floorplan_id, [])
    
    resolved = []
    for area_id in area_ids:
        resolved.append({
            "area_id": area_id,
            "floorplan_id": floorplan_id,
            "coordinates": _get_area_coordinates(floorplan_id, area_id)
        })
    
    return jsonify({
        "floorplan_id": floorplan_id,
        "areas": resolved,
        "total_zones": len(resolved)
    })

@areas_floorplan_bp.route("/<area_id>/navigate", methods=["GET"])
def navigate_to_floorplan(area_id: str):
    """Provides direct navigation data from area to floorplan coordinates."""
    floorplan_id = _area_floorplan_map.get(area_id)
    if not floorplan_id:
        return jsonify({"error": "No floorplan assigned"}), 404
    
    coords = _get_area_coordinates(floorplan_id, area_id)
    
    return jsonify({
        "area_id": area_id,
        "floorplan_id": floorplan_id,
        "coordinates": coords,
        "direct_url": f"/floorplan/{floorplan_id}?highlight={area_id}"
    })

def _get_zones_for_floorplan(floorplan_id: str) -> List[Dict[str, Any]]:
    """Helper to get zones for a floorplan."""
    area_ids = _floorplan_area_map.get(floorplan_id, [])
    return [{"area_id": aid, "name": f"Zone {aid}"} for aid in area_ids]

def _get_area_coordinates(floorplan_id: str, area_id: str) -> Dict[str, float]:
    """Helper to get coordinates for an area on a floorplan."""
    # Mock coordinates - in real implementation would come from floorplan data
    import hashlib
    hash_val = int(hashlib.md5(f"{floorplan_id}:{area_id}".encode()).hexdigest(), 16)
    return {
        "x": (hash_val % 100) / 100.0,  # 0.0-1.0
        "y": ((hash_val // 100) % 100) / 100.0,
        "width": 0.15,
        "height": 0.15
    }
