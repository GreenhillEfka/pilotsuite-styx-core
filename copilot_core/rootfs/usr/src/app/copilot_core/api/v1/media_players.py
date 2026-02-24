"""
Media Player API - PilotSuite v7.16.0

API for controlling media players.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

media_bp = Blueprint("media", __name__, url_prefix="/api/v1/media")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@media_bp.route("", methods=["GET"])
@require_token
def list_media_players():
    """List all media player entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        players = [s for s in hass.states.async_all() if s.domain == "media_player"]
        return jsonify({
            "ok": True,
            "media_players": [
                {
                    "entity_id": p.entity_id,
                    "state": p.state,
                    "volume_level": p.attributes.get("volume_level"),
                    "is_volume_muted": p.attributes.get("is_volume_muted"),
                    "media_title": p.attributes.get("media_title"),
                    "media_artist": p.attributes.get("media_artist"),
                    "friendly_name": p.attributes.get("friendly_name"),
                }
                for p in players
            ],
            "count": len(players),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@media_bp.route("/<player_id>/play", methods=["POST"])
@require_token
def media_play(player_id):
    """Play media."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("media_player", "media_play", {"entity_id": player_id})
        return jsonify({"ok": True, "entity_id": player_id, "state": "playing"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@media_bp.route("/<player_id>/pause", methods=["POST"])
@require_token
def media_pause(player_id):
    """Pause media."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("media_player", "media_pause", {"entity_id": player_id})
        return jsonify({"ok": True, "entity_id": player_id, "state": "paused"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@media_bp.route("/<player_id>/stop", methods=["POST"])
@require_token
def media_stop(player_id):
    """Stop media."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        hass.services.call("media_player", "media_stop", {"entity_id": player_id})
        return jsonify({"ok": True, "entity_id": player_id, "state": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@media_bp.route("/<player_id>/volume_set", methods=["POST"])
@require_token
def set_volume(player_id):
    """Set volume (0.0 - 1.0)."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    volume = data.get("volume")
    
    if volume is None:
        return jsonify({"error": "volume required (0.0-1.0)"}), 400
    
    try:
        hass.services.call("media_player", "volume_set", {
            "entity_id": player_id,
            "volume_level": float(volume)
        })
        return jsonify({"ok": True, "entity_id": player_id, "volume": volume})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@media_bp.route("/<player_id>/mute", methods=["POST"])
@require_token
def mute_volume(player_id):
    """Mute/unmute volume."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    data = request.get_json() or {}
    mute = data.get("mute", True)
    
    try:
        hass.services.call("media_player", "volume_mute", {
            "entity_id": player_id,
            "is_volume_muted": mute
        })
        return jsonify({"ok": True, "entity_id": player_id, "muted": mute})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
