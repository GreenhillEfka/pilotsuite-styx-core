"""Music Cloud API -- Sonos zone-following via motion sensors.

REST endpoints for the MusicCloudService that provides automatic speaker
grouping/ungrouping based on motion sensor events.

Blueprint prefix: /api/v1/media/cloud

All modifying endpoints require a valid auth token (Bearer or X-Auth-Token).

Endpoints:
    GET  /api/v1/media/cloud/zones          List zones with player/presence/group state
    POST /api/v1/media/cloud/zones/<id>/assign  Assign players to zone (delegates to MediaZoneManager)
    POST /api/v1/media/cloud/follow         Enable/disable music following
    GET  /api/v1/media/cloud/status         Current playback status per zone
    POST /api/v1/media/cloud/group          Manual group/ungroup speakers
    POST /api/v1/media/cloud/ungroup        Manual ungroup zones
    GET  /api/v1/media/cloud/favorites      Get favorites/playlists per zone
    POST /api/v1/media/cloud/favorites/<id> Set favorites for a zone
    POST /api/v1/media/cloud/motion         Webhook: motion detected in zone
    POST /api/v1/media/cloud/idle           Webhook: zone became idle
    GET  /api/v1/media/cloud/config         Get current config
    POST /api/v1/media/cloud/config         Update config
    GET  /api/v1/media/cloud/groups         List active speaker groups
    GET  /api/v1/media/cloud/events         Recent event log
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

media_cloud_bp = Blueprint(
    "media_cloud", __name__, url_prefix="/api/v1/media/cloud"
)

# Module-level service reference, set by init_music_cloud_api()
_music_cloud: Optional[Any] = None
_media_mgr: Optional[Any] = None


def init_music_cloud_api(music_cloud_service, media_zone_manager=None) -> None:
    """Wire MusicCloudService into the blueprint.

    Called from ``core_setup.register_blueprints()``.

    Parameters
    ----------
    music_cloud_service:
        A ``copilot_core.music_cloud.MusicCloudService`` instance.
    media_zone_manager:
        Optional ``copilot_core.media_zone_manager.MediaZoneManager`` for
        zone assignment delegation.
    """
    global _music_cloud, _media_mgr
    _music_cloud = music_cloud_service
    _media_mgr = media_zone_manager
    _LOGGER.info("Music Cloud API initialized")


def _require_service():
    """Return the MusicCloudService or a 503 error tuple."""
    if _music_cloud is None:
        return None, (jsonify({
            "ok": False,
            "error": "MusicCloudService not initialized",
        }), 503)
    return _music_cloud, None


# ===================================================================
# Zone Management
# ===================================================================

@media_cloud_bp.route("/zones", methods=["GET"])
@require_token
def get_zones():
    """List all media zones with player assignments, presence, and group state.

    Response::

        {
            "ok": true,
            "zones": {
                "living_room": {
                    "zone_id": "living_room",
                    "players": [...],
                    "presence": {"active": true, ...},
                    "group": {"group_id": "mcg_1", ...},
                    "playback_state": "playing"
                }
            },
            "config": {...},
            "active_groups": 1
        }
    """
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.get_zones_status()
    except Exception as exc:
        _LOGGER.exception("Failed to get zones status")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


@media_cloud_bp.route("/zones/<zone_id>/assign", methods=["POST"])
@require_token
def assign_player_to_zone(zone_id: str):
    """Assign a media player entity to a zone (delegates to MediaZoneManager).

    Request body::

        {
            "entity_id": "media_player.sonos_living_room",
            "role": "primary"    // optional
        }

    Response::

        {"ok": true, "zone_id": "living_room", "entity_id": "media_player.sonos_living_room"}
    """
    if _media_mgr is None:
        return jsonify({"ok": False, "error": "MediaZoneManager not available"}), 503

    data = request.get_json(silent=True) or {}
    entity_id = str(data.get("entity_id", "")).strip()

    if not entity_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'entity_id'",
        }), 400

    role = str(data.get("role", "primary")).strip()

    try:
        _media_mgr.assign_player(zone_id=zone_id, entity_id=entity_id, role=role)
    except Exception as exc:
        _LOGGER.exception("Failed to assign player %s to zone %s", entity_id, zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "entity_id": entity_id,
        "role": role,
    }), 201


# ===================================================================
# Music Following
# ===================================================================

@media_cloud_bp.route("/follow", methods=["POST"])
@require_token
def set_follow():
    """Enable or disable music following.

    Request body::

        {
            "enabled": true,
            "follow_timeout_sec": 300    // optional, 30-3600
        }

    Response::

        {"ok": true, "config": {...}}
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}

    if "enabled" not in data:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'enabled'",
        }), 400

    kwargs: dict[str, Any] = {"enabled": data["enabled"]}
    if "follow_timeout_sec" in data:
        kwargs["follow_timeout_sec"] = data["follow_timeout_sec"]
    if "auto_follow_on_motion" in data:
        kwargs["auto_follow_on_motion"] = data["auto_follow_on_motion"]
    if "auto_ungroup_on_idle" in data:
        kwargs["auto_ungroup_on_idle"] = data["auto_ungroup_on_idle"]

    try:
        config = svc.update_config(**kwargs)
    except Exception as exc:
        _LOGGER.exception("Failed to update follow config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "config": config})


# ===================================================================
# Playback Status
# ===================================================================

@media_cloud_bp.route("/status", methods=["GET"])
@require_token
def get_status():
    """Get current playback status per zone with active group information.

    Response::

        {
            "ok": true,
            "zone_states": {
                "living_room": {"state": "playing", ...},
                "bedroom": {"state": "idle", ...}
            },
            "active_groups": [...],
            "follow_enabled": true
        }
    """
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.get_playback_status()
    except Exception as exc:
        _LOGGER.exception("Failed to get playback status")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


# ===================================================================
# Manual Group / Ungroup
# ===================================================================

@media_cloud_bp.route("/group", methods=["POST"])
@require_token
def manual_group():
    """Manually group target zones' speakers with a source zone.

    Request body::

        {
            "source_zone": "living_room",
            "target_zones": ["kitchen", "bedroom"],
            "coordinator_entity": "media_player.sonos_living"  // optional
        }

    Response::

        {
            "ok": true,
            "source_zone": "living_room",
            "coordinator": "media_player.sonos_living",
            "results": [...]
        }
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    source_zone = str(data.get("source_zone", "")).strip()
    target_zones = data.get("target_zones", [])
    coordinator = str(data.get("coordinator_entity", "")).strip() or None

    if not source_zone:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'source_zone'",
        }), 400

    if not isinstance(target_zones, list) or not target_zones:
        return jsonify({
            "ok": False,
            "error": "Missing or empty field 'target_zones' (expected non-empty list)",
        }), 400

    try:
        result = svc.manual_group(
            source_zone=source_zone,
            target_zones=target_zones,
            coordinator_entity=coordinator,
        )
    except Exception as exc:
        _LOGGER.exception("Failed to manually group zones")
        return jsonify({"ok": False, "error": str(exc)}), 500

    if isinstance(result, dict) and not result.get("ok"):
        return jsonify(result), 400

    return jsonify(result)


@media_cloud_bp.route("/ungroup", methods=["POST"])
@require_token
def manual_ungroup():
    """Manually ungroup specified zones.

    Request body::

        {
            "zone_ids": ["kitchen", "bedroom"]
        }

    Response::

        {"ok": true, "results": [...]}
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    zone_ids = data.get("zone_ids", [])

    if not isinstance(zone_ids, list) or not zone_ids:
        return jsonify({
            "ok": False,
            "error": "Missing or empty field 'zone_ids' (expected non-empty list)",
        }), 400

    try:
        result = svc.manual_ungroup(zone_ids=zone_ids)
    except Exception as exc:
        _LOGGER.exception("Failed to manually ungroup zones")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


# ===================================================================
# Favorites / Playlists
# ===================================================================

@media_cloud_bp.route("/favorites", methods=["GET"])
@require_token
def get_all_favorites():
    """Get favorites/playlists for all zones.

    Response::

        {
            "ok": true,
            "zones": {
                "living_room": ["Jazz Mix", "Chill Lounge", ...],
                "bedroom": [...]
            }
        }
    """
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.get_all_favorites()
    except Exception as exc:
        _LOGGER.exception("Failed to get favorites")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


@media_cloud_bp.route("/favorites/<zone_id>", methods=["GET"])
@require_token
def get_zone_favorites(zone_id: str):
    """Get favorites for a specific zone.

    Response::

        {
            "ok": true,
            "zone_id": "living_room",
            "favorites": ["Jazz Mix", "Chill Lounge"],
            "local_count": 1,
            "ha_count": 2
        }
    """
    svc, err = _require_service()
    if err:
        return err

    try:
        result = svc.get_zone_favorites(zone_id)
    except Exception as exc:
        _LOGGER.exception("Failed to get favorites for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


@media_cloud_bp.route("/favorites/<zone_id>", methods=["POST"])
@require_token
def set_zone_favorites(zone_id: str):
    """Set locally stored favorites for a zone.

    Request body::

        {
            "favorites": ["Jazz Mix", "Morning Coffee", "Focus Beats"]
        }

    Response::

        {"ok": true, "zone_id": "living_room", "favorites": [...]}
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    favorites = data.get("favorites")

    if not isinstance(favorites, list):
        return jsonify({
            "ok": False,
            "error": "Missing or invalid field 'favorites' (expected list of strings)",
        }), 400

    try:
        result = svc.set_zone_favorites(zone_id, favorites)
    except Exception as exc:
        _LOGGER.exception("Failed to set favorites for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


# ===================================================================
# Webhook: Motion / Idle Events
# ===================================================================

@media_cloud_bp.route("/motion", methods=["POST"])
@require_token
def on_motion():
    """Webhook endpoint: motion detected in a zone.

    Called by HA automation when a motion sensor triggers. This is the
    main entry point for the zone-following logic.

    Request body::

        {
            "zone_id": "kitchen",
            "person_id": "person.alice",        // optional
            "sensor_entity_id": "binary_sensor.kitchen_motion"  // optional
        }

    Response::

        {
            "ok": true,
            "action": "grouped",
            "group_id": "mcg_1",
            "source_zone": "living_room",
            "target_zone": "kitchen",
            "coordinator": "media_player.sonos_living",
            "joined_entities": ["media_player.sonos_kitchen"]
        }
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    zone_id = str(data.get("zone_id", "")).strip()

    if not zone_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'zone_id'",
        }), 400

    person_id = str(data.get("person_id", "")).strip()
    sensor_entity_id = str(data.get("sensor_entity_id", "")).strip()

    try:
        result = svc.on_motion_detected(
            zone_id=zone_id,
            person_id=person_id,
            sensor_entity_id=sensor_entity_id,
        )
    except Exception as exc:
        _LOGGER.exception("Failed to process motion event for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


@media_cloud_bp.route("/idle", methods=["POST"])
@require_token
def on_idle():
    """Webhook endpoint: zone became idle (no more motion/presence).

    Called when a zone's occupancy sensor clears or motion timeout expires.

    Request body::

        {
            "zone_id": "kitchen"
        }

    Response::

        {
            "ok": true,
            "action": "ungrouped",
            "zone_id": "kitchen",
            "ungrouped_entities": ["media_player.sonos_kitchen"]
        }
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    zone_id = str(data.get("zone_id", "")).strip()

    if not zone_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'zone_id'",
        }), 400

    try:
        result = svc.on_zone_idle(zone_id=zone_id)
    except Exception as exc:
        _LOGGER.exception("Failed to process idle event for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result)


# ===================================================================
# Config
# ===================================================================

@media_cloud_bp.route("/config", methods=["GET"])
@require_token
def get_config():
    """Get current Music Cloud configuration.

    Response::

        {
            "ok": true,
            "config": {
                "enabled": true,
                "follow_timeout_sec": 300,
                "auto_follow_on_motion": true,
                "auto_ungroup_on_idle": true,
                "zone_overrides": {},
                "zone_favorites": {}
            }
        }
    """
    svc, err = _require_service()
    if err:
        return err

    try:
        config = svc.get_config()
    except Exception as exc:
        _LOGGER.exception("Failed to get config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "config": config})


@media_cloud_bp.route("/config", methods=["POST"])
@require_token
def update_config():
    """Update Music Cloud configuration.

    Request body (all fields optional)::

        {
            "enabled": true,
            "follow_timeout_sec": 300,
            "auto_follow_on_motion": true,
            "auto_ungroup_on_idle": true,
            "zone_overrides": {
                "bedroom": {"timeout": 600, "enabled": false}
            }
        }

    Response::

        {"ok": true, "config": {...}}
    """
    svc, err = _require_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}

    if not data:
        return jsonify({
            "ok": False,
            "error": "Request body must contain at least one config field",
        }), 400

    try:
        config = svc.update_config(**data)
    except Exception as exc:
        _LOGGER.exception("Failed to update config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "config": config})


# ===================================================================
# Active Groups
# ===================================================================

@media_cloud_bp.route("/groups", methods=["GET"])
@require_token
def get_groups():
    """List active speaker groups.

    Response::

        {
            "ok": true,
            "groups": [
                {
                    "group_id": "mcg_1",
                    "source_zone": "living_room",
                    "coordinator": "media_player.sonos_living",
                    "grouped_zones": ["kitchen"],
                    "grouped_entities": ["media_player.sonos_kitchen"],
                    "created_at": 1700000000.0,
                    "last_updated": 1700000030.0
                }
            ]
        }
    """
    svc, err = _require_service()
    if err:
        return err

    try:
        groups = svc.get_active_groups()
    except Exception as exc:
        _LOGGER.exception("Failed to get active groups")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "groups": groups})


# ===================================================================
# Event Log
# ===================================================================

@media_cloud_bp.route("/events", methods=["GET"])
@require_token
def get_events():
    """Get recent Music Cloud events (motion, grouping, ungrouping).

    Query params:
        limit (int): Max events to return (1-200, default 50).

    Response::

        {
            "ok": true,
            "events": [
                {
                    "event_type": "zone_grouped",
                    "zone_id": "kitchen",
                    "timestamp": 1700000000.0,
                    "source_zone": "living_room",
                    ...
                }
            ]
        }
    """
    svc, err = _require_service()
    if err:
        return err

    try:
        limit = max(1, min(200, int(request.args.get("limit", 50))))
    except (TypeError, ValueError):
        limit = 50

    try:
        events = svc.get_event_log(limit=limit)
    except Exception as exc:
        _LOGGER.exception("Failed to get events")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "events": events})
