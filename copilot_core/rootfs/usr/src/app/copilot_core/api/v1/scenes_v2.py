"""
Scenes v2 API - PilotSuite v7.17.0

Enhanced Scenes API with pattern learning integration.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

scenes_v2_bp = Blueprint("scenes_v2", __name__, url_prefix="/api/v1/scenes/v2")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


def _get_scene_extractor():
    try:
        from copilot_core.scene_patterns import get_scene_pattern_extractor
        return get_scene_pattern_extractor()
    except Exception:
        return None


@scenes_v2_bp.route("", methods=["GET"])
@require_token
def list_scenes_v2():
    """List all scenes with enhanced info."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        scenes = [s for s in hass.states.async_all() if s.domain == "scene"]
        
        # Get pattern suggestions
        extractor = _get_scene_extractor()
        suggestions = extractor.suggest_scenes() if extractor else []
        
        return jsonify({
            "ok": True,
            "scenes": [
                {
                    "entity_id": s.entity_id,
                    "friendly_name": s.attributes.get("friendly_name"),
                    "active": s.state == "scening",
                }
                for s in scenes
            ],
            "suggestions": suggestions[:5],
            "count": len(scenes),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scenes_v2_bp.route("/<scene_id>/activate", methods=["POST"])
@require_token
def activate_scene(scene_id):
    """Activate a scene and record the pattern."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        # Activate scene
        hass.services.call("scene", "turn_on", {"entity_id": scene_id})
        
        # Record pattern
        extractor = _get_scene_extractor()
        if extractor:
            extractor.record_scene_activation(scene_id)
        
        return jsonify({
            "ok": True,
            "scene_id": scene_id,
            "message": "Scene activated and pattern recorded",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@scenes_v2_bp.route("/suggest", methods=["GET"])
@require_token
def suggest_scenes():
    """Get scene suggestions based on learned patterns."""
    extractor = _get_scene_extractor()
    if not extractor:
        return jsonify({"error": "Pattern extractor not available"}), 503
    
    suggestions = extractor.suggest_scenes()
    
    return jsonify({
        "ok": True,
        "suggestions": suggestions,
        "count": len(suggestions),
    })
