"""Habitus Zone Admin API — Vertical Slice Phase 2.
Full CRUD + Symbiosis management for Habitus Zones.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("habitus_admin", __name__, url_prefix="/api/v1/habitus")

# In-Memory Store (wird später durch DB ersetzt)
_zones: Dict[str, dict] = {}
_device_links: Dict[str, dict] = {}
_habitus_rules: Dict[str, dict] = {}

@bp.route("/zones", methods=["GET"])
def list_zones():
    """List all Habitus Zones."""
    return jsonify({"ok": True, "zones": list(_zones.values()), "count": len(_zones)})

@bp.route("/zones", methods=["POST"])
def create_zone():
    """Create or update a Habitus Zone."""
    data = request.get_json() or {}
    zone_id = data.get("zone_id")
    if not zone_id:
        return jsonify({"ok": False, "error": "zone_id required"}), 400
    
    _zones[zone_id] = {
        "zone_id": zone_id,
        "name": data.get("name", zone_id),
        "ha_area_id": data.get("ha_area_id"),
        "linked_entities": data.get("linked_entities", []),
        "habitus_rules": data.get("habitus_rules", []),
        "active_context": data.get("active_context", "ready"),
        "metadata": data.get("metadata", {})
    }
    _LOGGER.info(f"Created/updated Habitus Zone: {zone_id}")
    return jsonify({"ok": True, "zone": _zones[zone_id]})

@bp.route("/zones/<zone_id>", methods=["GET"])
def get_zone(zone_id):
    """Get single Habitus Zone detail."""
    zone = _zones.get(zone_id)
    if not zone:
        return jsonify({"ok": False, "error": "Zone not found"}), 404
    return jsonify({"ok": True, "zone": zone})

@bp.route("/zones/<zone_id>", methods=["DELETE"])
def delete_zone(zone_id):
    """Delete a Habitus Zone."""
    if zone_id in _zones:
        del _zones[zone_id]
        _LOGGER.info(f"Deleted Habitus Zone: {zone_id}")
        return jsonify({"ok": True, "deleted": zone_id})
    return jsonify({"ok": False, "error": "Zone not found"}), 404

@bp.route("/zones/<zone_id>/link", methods=["POST"])
def link_device(zone_id):
    """Link a device/entity to a Habitus Zone."""
    if zone_id not in _zones:
        return jsonify({"ok": False, "error": "Zone not found"}), 404
    
    data = request.get_json() or {}
    entity_id = data.get("entity_id")
    if not entity_id:
        return jsonify({"ok": False, "error": "entity_id required"}), 400
    
    if entity_id not in _zones[zone_id]["linked_entities"]:
        _zones[zone_id]["linked_entities"].append(entity_id)
    
    _device_links[f"{zone_id}:{entity_id}"] = {
        "zone_id": zone_id,
        "entity_id": entity_id,
        "linked_at": "now"
    }
    _LOGGER.info(f"Linked device {entity_id} to Zone {zone_id}")
    return jsonify({"ok": True, "linked": entity_id})

@bp.route("/zones/<zone_id>/rules", methods=["POST"])
def add_habitus_rule(zone_id):
    """Add a Habitus rule to a Zone."""
    if zone_id not in _zones:
        return jsonify({"ok": False, "error": "Zone not found"}), 404
    
    data = request.get_json() or {}
    rule = {
        "rule_id": data.get("rule_id", f"rule_{len(_habitus_rules)}"),
        "trigger": data.get("trigger"),
        "condition": data.get("condition"),
        "action": data.get("action")
    }
    
    _zones[zone_id]["habitus_rules"].append(rule["rule_id"])
    _habitus_rules[rule["rule_id"]] = rule
    _LOGGER.info(f"Added Habitus rule {rule['rule_id']} to Zone {zone_id}")
    return jsonify({"ok": True, "rule": rule})

@bp.route("/zones/<zone_id>/context", methods=["POST"])
def set_zone_context(zone_id):
    """Set active context for a Zone."""
    if zone_id not in _zones:
        return jsonify({"ok": False, "error": "Zone not found"}), 404
    
    data = request.get_json() or {}
    _zones[zone_id]["active_context"] = data.get("context", "ready")
    _LOGGER.info(f"Set context for Zone {zone_id}: {_zones[zone_id]['active_context']}")
    return jsonify({"ok": True, "zone_id": zone_id, "context": _zones[zone_id]["active_context"]})

@bp.route("/zones/<zone_id>/sync", methods=["POST"])
def trigger_zone_sync(zone_id):
    """Trigger manual sync with HA for a Zone."""
    if zone_id not in _zones:
        return jsonify({"ok": False, "error": "Zone not found"}), 404
    
    # TODO: Call actual sync logic from symbiosis layer
    _zones[zone_id]["last_sync"] = "now"
    return jsonify({"ok": True, "synced": zone_id})

@bp.route("/zones/summary", methods=["GET"])
def zones_summary():
    """Get summary of all Zones."""
    total = len(_zones)
    with_links = sum(1 for z in _zones.values() if z.get("linked_entities"))
    with_rules = sum(1 for z in _zones.values() if z.get("habitus_rules"))
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_zones": total,
            "zones_with_links": with_links,
            "zones_with_rules": with_rules,
            "total_device_links": len(_device_links),
            "total_habitus_rules": len(_habitus_rules)
        }
    })
