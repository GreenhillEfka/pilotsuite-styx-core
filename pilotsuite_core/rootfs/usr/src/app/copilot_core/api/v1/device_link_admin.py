"""Device Link Admin API — Vertical Slice Phase 2.
Full CRUD + capability management for Device Links.
"""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Dict, List

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("device_link_admin", __name__, url_prefix="/api/v1/devices")

# In-Memory Store
_links: Dict[str, dict] = {}

@bp.route("/links", methods=["GET"])
def list_device_links():
    """List all Device Links."""
    return jsonify({"ok": True, "links": list(_links.values()), "count": len(_links)})

@bp.route("/links", methods=["POST"])
def create_device_link():
    """Create or update a Device Link."""
    data = request.get_json() or {}
    link_id = data.get("link_id")
    if not link_id:
        return jsonify({"ok": False, "error": "link_id required"}), 400
    
    _links[link_id] = {
        "link_id": link_id,
        "ha_entity_id": data.get("ha_entity_id"),
        "name": data.get("name", link_id),
        "domain": data.get("domain"),
        "capabilities": data.get("capabilities", []),
        "zone_ref": data.get("zone_ref"),
        "last_state": data.get("last_state", {}),
        "linked_at": "now"
    }
    _LOGGER.info(f"Created/updated Device Link: {link_id}")
    return jsonify({"ok": True, "link": _links[link_id]})

@bp.route("/links/<link_id>", methods=["GET"])
def get_device_link(link_id):
    """Get single Device Link detail."""
    link = _links.get(link_id)
    if not link:
        return jsonify({"ok": False, "error": "Link not found"}), 404
    return jsonify({"ok": True, "link": link})

@bp.route("/links/<link_id>", methods=["DELETE"])
def delete_device_link(link_id):
    """Delete a Device Link."""
    if link_id in _links:
        del _links[link_id]
        _LOGGER.info(f"Deleted Device Link: {link_id}")
        return jsonify({"ok": True, "deleted": link_id})
    return jsonify({"ok": False, "error": "Link not found"}), 404

@bp.route("/links/<link_id>/capabilities", methods=["GET"])
def get_device_capabilities(link_id):
    """Get capabilities for a Device Link."""
    link = _links.get(link_id)
    if not link:
        return jsonify({"ok": False, "error": "Link not found"}), 404
    return jsonify({"ok": True, "link_id": link_id, "capabilities": link.get("capabilities", [])})

@bp.route("/links/<link_id>/zone", methods=["POST"])
def link_to_zone(link_id):
    """Link a device to a Habitus Zone."""
    if link_id not in _links:
        return jsonify({"ok": False, "error": "Link not found"}), 404
    
    data = request.get_json() or {}
    zone_ref = data.get("zone_ref")
    if not zone_ref:
        return jsonify({"ok": False, "error": "zone_ref required"}), 400
    
    _links[link_id]["zone_ref"] = zone_ref
    _LOGGER.info(f"Linked device {link_id} to zone {zone_ref}")
    return jsonify({"ok": True, "link_id": link_id, "zone_ref": zone_ref})

@bp.route("/links/by_domain", methods=["GET"])
def get_links_by_domain():
    """Get Device Links grouped by domain."""
    by_domain: Dict[str, List] = {}
    for link in _links.values():
        domain = link.get("domain", "unknown")
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(link)
    
    return jsonify({"ok": True, "by_domain": by_domain})

@bp.route("/links/summary", methods=["GET"])
def device_links_summary():
    """Get summary of all Device Links."""
    total = len(_links)
    by_domain: Dict[str, int] = {}
    with_zone = sum(1 for l in _links.values() if l.get("zone_ref"))
    
    for link in _links.values():
        domain = link.get("domain", "unknown")
        by_domain[domain] = by_domain.get(domain, 0) + 1
    
    return jsonify({
        "ok": True,
        "summary": {
            "total_links": total,
            "links_with_zone": with_zone,
            "by_domain": by_domain
        }
    })
