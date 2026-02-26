"""
Scenes v2 API — Enhanced scenes with pattern learning and AI suggestions.

Builds on the v1 scene store with intelligent scene suggestions,
pattern-based learning, and HA Supervisor integration for activation.
"""

from flask import Blueprint, jsonify, request
import logging
import os
import time

import requests as http_requests

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

scenes_v2_bp = Blueprint("scenes_v2", __name__, url_prefix="/api/v1/scenes/v2")


def _get_scene_cache():
    """Get the scene cache from the v1 API module."""
    try:
        from copilot_core.api.v1.scenes import _scene_cache
        return _scene_cache
    except ImportError:
        return {}


def _get_scene_extractor():
    try:
        from copilot_core.scene_patterns import get_scene_pattern_extractor
        return get_scene_pattern_extractor()
    except Exception:
        return None


def _get_ha_headers():
    """Return HA Supervisor API headers."""
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not ha_token:
        return None, None
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    return ha_url, headers


@scenes_v2_bp.route("", methods=["GET"])
@require_token
def list_scenes_v2():
    """List all scenes with pattern suggestions and zone grouping."""
    scene_cache = _get_scene_cache()
    zone_id = request.args.get("zone_id")

    scenes = list(scene_cache.values())
    if zone_id:
        scenes = [s for s in scenes if s.get("zone_id") == zone_id]

    # Sort by last_applied (most recent first), then by created_at
    scenes.sort(key=lambda s: s.get("last_applied") or s.get("created_at") or 0, reverse=True)

    # Get pattern suggestions
    extractor = _get_scene_extractor()
    suggestions = []
    if extractor:
        try:
            suggestions = extractor.suggest_scenes()[:5]
        except Exception:
            logger.debug("Could not get scene suggestions", exc_info=True)

    # Group by zone
    zones: dict[str, list] = {}
    for s in scenes:
        zname = s.get("zone_name", s.get("zone_id", "Unbekannt"))
        zones.setdefault(zname, []).append({
            "scene_id": s.get("scene_id"),
            "name": s.get("name"),
            "zone_id": s.get("zone_id"),
            "source": s.get("source", "manual"),
            "is_favorite": s.get("is_favorite", False),
            "applied_count": s.get("applied_count", 0),
            "last_applied": s.get("last_applied"),
            "created_at": s.get("created_at"),
            "entity_count": len(s.get("entity_states", {})),
        })

    return jsonify({
        "ok": True,
        "scenes": scenes,
        "zones": zones,
        "suggestions": suggestions,
        "count": len(scenes),
    })


@scenes_v2_bp.route("/<scene_id>/activate", methods=["POST"])
@require_token
def activate_scene(scene_id):
    """Activate a scene via HA Supervisor and record the pattern."""
    scene_cache = _get_scene_cache()
    scene = scene_cache.get(scene_id)
    if not scene:
        return jsonify({"error": f"Szene '{scene_id}' nicht gefunden"}), 404

    ha_url, headers = _get_ha_headers()
    if not headers:
        return jsonify({"error": "No SUPERVISOR_TOKEN"}), 503

    success = False
    method = "none"

    # Try HA scene.turn_on first
    ha_scene_eid = scene.get("ha_scene_entity_id")
    if ha_scene_eid:
        try:
            resp = http_requests.post(
                f"{ha_url}/services/scene/turn_on",
                json={"entity_id": ha_scene_eid},
                headers=headers, timeout=10,
            )
            if resp.ok:
                success = True
                method = "ha_scene"
        except Exception:
            logger.debug("HA scene turn_on failed for %s", scene_id)

    # Fallback: apply via scene.apply service
    if not success:
        entity_states = scene.get("entity_states", {})
        if entity_states:
            try:
                resp = http_requests.post(
                    f"{ha_url}/services/scene/apply",
                    json={"entities": entity_states, "transition": 1.0},
                    headers=headers, timeout=10,
                )
                if resp.ok:
                    success = True
                    method = "scene_apply"
            except Exception:
                logger.debug("scene.apply failed for %s", scene_id)

    # Update counts
    scene["applied_count"] = scene.get("applied_count", 0) + 1
    scene["last_applied"] = time.time()

    # Persist
    try:
        from copilot_core.api.v1.scenes import _save_scenes_to_disk, _scene_lock
        with _scene_lock:
            _save_scenes_to_disk()
    except Exception:
        pass

    # Record pattern
    extractor = _get_scene_extractor()
    if extractor:
        try:
            body = request.get_json(silent=True) or {}
            extractor.record_scene_activation(
                scene_id,
                context=body.get("context"),
            )
        except Exception:
            logger.debug("Could not record scene pattern", exc_info=True)

    return jsonify({
        "ok": success,
        "scene_id": scene_id,
        "method": method,
        "applied_count": scene["applied_count"],
    })


@scenes_v2_bp.route("/<scene_id>/favorite", methods=["POST"])
@require_token
def toggle_favorite(scene_id):
    """Toggle favorite status for a scene."""
    scene_cache = _get_scene_cache()
    scene = scene_cache.get(scene_id)
    if not scene:
        return jsonify({"error": f"Szene '{scene_id}' nicht gefunden"}), 404

    scene["is_favorite"] = not scene.get("is_favorite", False)

    try:
        from copilot_core.api.v1.scenes import _save_scenes_to_disk, _scene_lock
        with _scene_lock:
            _save_scenes_to_disk()
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "scene_id": scene_id,
        "is_favorite": scene["is_favorite"],
    })


@scenes_v2_bp.route("/suggest", methods=["GET"])
@require_token
def suggest_scenes():
    """Get scene suggestions based on learned patterns and current context."""
    extractor = _get_scene_extractor()
    if not extractor:
        return jsonify({"ok": True, "suggestions": [], "count": 0})

    context = request.args.get("context")
    suggestions = extractor.suggest_scenes(context=context) if hasattr(extractor.suggest_scenes, '__code__') and 'context' in extractor.suggest_scenes.__code__.co_varnames else extractor.suggest_scenes()

    return jsonify({
        "ok": True,
        "suggestions": suggestions[:5],
        "count": len(suggestions),
    })
