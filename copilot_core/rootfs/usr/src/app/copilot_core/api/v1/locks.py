"""
Locks API - PilotSuite v7.21.0

API for controlling locks.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

locks_bp = Blueprint("locks", __name__, url_prefix="/api/v1/locks")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@locks_bp.route("", methods=["GET"])
@require_token
def list_locks():
    """List all lock entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        locks = [s for s in hass.states.async_all() if s.domain == "lock"]
        return jsonify({
            "ok": True,
            "locks": [
                {
                    "entity_id": l.entity_id,
                    "state": l.state,
                    "friendly_name": l.attributes.get("friendly_name"),
                }
                for l in locks
            ],
            "count": len(locks),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@locks_bp.route("/<lock_id>/lock", methods=["POST"])
@require_token
def lock_lock(lock_id):
    """Lock a lock."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("lock", "lock", {"entity_id": lock_id})
        return jsonify({"ok": True, "entity_id": lock_id, "state": "locked"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@locks_bp.route("/<lock_id>/unlock", methods=["POST"])
@require_token
def unlock_lock(lock_id):
    """Unlock a lock."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("lock", "unlock", {"entity_id": lock_id})
        return jsonify({"ok": True, "entity_id": lock_id, "state": "unlocked"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
