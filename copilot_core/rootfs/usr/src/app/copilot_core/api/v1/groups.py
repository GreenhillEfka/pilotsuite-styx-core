"""
Groups API - PilotSuite v7.16.0

API for managing device groups.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

groups_bp = Blueprint("groups", __name__, url_prefix="/api/v1/groups")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@groups_bp.route("", methods=["GET"])
@require_token
def list_groups():
    """List all HA groups."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        groups = [s for s in hass.states.async_all() if s.domain == "group"]
        return jsonify({
            "ok": True,
            "groups": [
                {
                    "entity_id": g.entity_id,
                    "state": g.state,
                    "attributes": dict(g.attributes) if g.attributes else {},
                }
                for g in groups
            ],
            "count": len(groups),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@groups_bp.route("/<group_id>", methods=["GET"])
@require_token
def get_group(group_id):
    """Get group details."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        state = hass.states.get(f"group.{group_id}")
        if not state:
            return jsonify({"error": "Group not found"}), 404
        
        return jsonify({
            "ok": True,
            "entity_id": state.entity_id,
            "state": state.state,
            "attributes": dict(state.attributes) if state.attributes else {},
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@groups_bp.route("/<group_id>/turn_on", methods=["POST"])
@require_token
def group_turn_on(group_id):
    """Turn on all entities in a group."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("homeassistant", "turn_on", {"entity_id": f"group.{group_id}"})
        return jsonify({"ok": True, "group": group_id, "state": "on"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@groups_bp.route("/<group_id>/turn_off", methods=["POST"])
@require_token
def group_turn_off(group_id):
    """Turn off all entities in a group."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("homeassistant", "turn_off", {"entity_id": f"group.{group_id}"})
        return jsonify({"ok": True, "group": group_id, "state": "off"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@groups_bp.route("/create", methods=["POST"])
@require_token
def create_group():
    """Create a new group."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    name = data.get("name")
    entities = data.get("entities", [])
    
    if not name or not entities:
        return jsonify({"error": "name and entities required"}), 400
    
    try:
        # Use group.set service
        hass.services.call("group", "set", {
            "object_id": name.lower().replace(" ", "_"),
            "name": name,
            "entities": ",".join(entities),
        })
        return jsonify({"ok": True, "name": name, "entities": entities})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
