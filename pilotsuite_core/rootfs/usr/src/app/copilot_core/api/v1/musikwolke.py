"""API v1 blueprint for Musikwolke (Music Cloud) control.

Exposes the MusikwolkeBridge for zone-based music control via Sonos.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

musikwolke_bp = Blueprint("musikwolke", __name__, url_prefix="/api/v1/musikwolke")

_bridge = None

_ZONE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")


def _json_error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _bridge_unavailable():
    return _json_error("musikwolke_not_available", 503)


def _handle_bridge_exception(action: str, exc: Exception):
    _LOGGER.exception("Musikwolke API action failed: %s", action)
    return _json_error(str(exc), 500)


def _validate_zone_id(zone_id: str) -> bool:
    """Validate zone_id is alphanumeric, max 50 chars."""
    return bool(_ZONE_ID_RE.match(zone_id))


def _require_json_object(*, required: bool = True):
    data = request.get_json(silent=True)
    if data is None:
        if required:
            return None, _json_error("Request body required", 400)
        return {}, None
    if not isinstance(data, dict):
        return None, _json_error("JSON body must be an object", 400)
    return data, None


def _parse_volume_pct(value: Any, *, required: bool = False):
    if value is None:
        if required:
            return None, _json_error("volume_pct required", 400)
        return None, None
    try:
        volume = int(value)
    except (TypeError, ValueError):
        return None, _json_error("volume_pct must be an integer", 400)
    if not 0 <= volume <= 100:
        return None, _json_error("volume_pct must be between 0 and 100", 400)
    return volume, None


def _normalize_zone_ids(value: Any, *, min_length: int):
    if not isinstance(value, list):
        return None, _json_error("zone_ids must be a list", 400)
    if len(value) < min_length:
        return None, _json_error(f"need at least {min_length} zones", 400)

    zone_ids: list[str] = []
    for raw_zone_id in value:
        if not isinstance(raw_zone_id, str):
            return None, _json_error("zone_ids must contain strings", 400)
        zone_id = raw_zone_id.strip()
        if not _validate_zone_id(zone_id):
            return None, _json_error("Invalid zone_id in list", 400)
        zone_ids.append(zone_id)
    return zone_ids, None


def init_musikwolke_api(bridge) -> None:
    """Wire the MusikwolkeBridge into this blueprint."""
    global _bridge  # noqa: PLW0603
    _bridge = bridge


@musikwolke_bp.route("/status", methods=["GET"])
@require_token
def get_status():
    """Get Musikwolke status (Sonos speakers, active zones, media follow)."""
    if not _bridge:
        return _bridge_unavailable()
    try:
        return jsonify({"ok": True, **_bridge.get_status()})
    except Exception as exc:
        return _handle_bridge_exception("status", exc)


@musikwolke_bp.route("/zone-map", methods=["GET"])
@require_token
def get_zone_map():
    """Get zone-to-speaker mapping."""
    if not _bridge:
        return _bridge_unavailable()
    try:
        return jsonify({"ok": True, "zone_speaker_map": _bridge.get_zone_speaker_map()})
    except Exception as exc:
        return _handle_bridge_exception("zone_map.get", exc)


@musikwolke_bp.route("/zone-map", methods=["POST"])
@require_token
def set_zone_speaker():
    """Set a zone-to-speaker mapping.

    Body: {"zone_id": "...", "sonos_room": "..."}
    """
    if not _bridge:
        return _bridge_unavailable()

    data, err = _require_json_object()
    if err:
        return err

    zone_id = str(data.get("zone_id", "")).strip()
    sonos_room = str(data.get("sonos_room", "")).strip()

    if not zone_id or not sonos_room:
        return _json_error("zone_id and sonos_room required", 400)

    if not _validate_zone_id(zone_id):
        return _json_error("Invalid zone_id format", 400)

    try:
        _bridge.set_zone_speaker(zone_id, sonos_room)
        return jsonify({"ok": True, "zone_id": zone_id, "sonos_room": sonos_room})
    except Exception as exc:
        return _handle_bridge_exception("zone_map.set", exc)


@musikwolke_bp.route("/auto-discover", methods=["POST"])
@require_token
def auto_discover():
    """Auto-discover Sonos speakers and map them to zones."""
    if not _bridge:
        return _bridge_unavailable()

    try:
        mapped = _bridge.auto_discover_mappings()
        return jsonify({
            "ok": True,
            "mapped": mapped,
            "zone_speaker_map": _bridge.get_zone_speaker_map(),
        })
    except Exception as exc:
        return _handle_bridge_exception("auto_discover", exc)


@musikwolke_bp.route("/play/<zone_id>", methods=["POST"])
@require_token
def play_zone(zone_id: str):
    """Play music in a zone."""
    if not _bridge:
        return _bridge_unavailable()

    if not _validate_zone_id(zone_id):
        return _json_error("Invalid zone_id format", 400)

    data, err = _require_json_object(required=False)
    if err:
        return err

    volume, volume_err = _parse_volume_pct(data.get("volume_pct"), required=False)
    if volume_err:
        return volume_err

    try:
        success = _bridge.play_in_zone(zone_id, volume)
        return jsonify({"ok": success, "zone_id": zone_id, "action": "play"})
    except Exception as exc:
        return _handle_bridge_exception("play", exc)


@musikwolke_bp.route("/pause/<zone_id>", methods=["POST"])
@require_token
def pause_zone(zone_id: str):
    """Pause music in a zone."""
    if not _bridge:
        return _bridge_unavailable()

    if not _validate_zone_id(zone_id):
        return _json_error("Invalid zone_id format", 400)

    try:
        success = _bridge.pause_in_zone(zone_id)
        return jsonify({"ok": success, "zone_id": zone_id, "action": "pause"})
    except Exception as exc:
        return _handle_bridge_exception("pause", exc)


@musikwolke_bp.route("/volume/<zone_id>", methods=["POST"])
@require_token
def set_volume(zone_id: str):
    """Set volume for a zone. Body: {"volume_pct": 30}"""
    if not _bridge:
        return _bridge_unavailable()

    if not _validate_zone_id(zone_id):
        return _json_error("Invalid zone_id format", 400)

    data, err = _require_json_object(required=False)
    if err:
        return err

    volume, volume_err = _parse_volume_pct(data.get("volume_pct", 30), required=True)
    if volume_err:
        return volume_err

    try:
        success = _bridge.set_zone_volume(zone_id, volume)
        return jsonify({"ok": success, "zone_id": zone_id, "volume_pct": volume})
    except Exception as exc:
        return _handle_bridge_exception("volume", exc)


@musikwolke_bp.route("/create", methods=["POST"])
@require_token
def create_musikwolke():
    """Create a Musikwolke across zones. Body: {"zone_ids": ["z1", "z2", ...]}"""
    if not _bridge:
        return _bridge_unavailable()

    data, err = _require_json_object()
    if err:
        return err

    zone_ids, zone_err = _normalize_zone_ids(data.get("zone_ids"), min_length=2)
    if zone_err:
        return zone_err

    try:
        success = _bridge.create_musikwolke(zone_ids)
        return jsonify({"ok": success, "zone_ids": zone_ids})
    except Exception as exc:
        return _handle_bridge_exception("create", exc)


@musikwolke_bp.route("/dissolve", methods=["POST"])
@require_token
def dissolve_musikwolke():
    """Dissolve a Musikwolke. Body: {"zone_ids": ["z1", "z2", ...]}"""
    if not _bridge:
        return _bridge_unavailable()

    data, err = _require_json_object()
    if err:
        return err

    zone_ids, zone_err = _normalize_zone_ids(data.get("zone_ids"), min_length=1)
    if zone_err:
        return zone_err

    try:
        success = _bridge.dissolve_musikwolke(zone_ids)
        return jsonify({"ok": success, "zone_ids": zone_ids})
    except Exception as exc:
        return _handle_bridge_exception("dissolve", exc)


@musikwolke_bp.route("/favorites", methods=["GET"])
@require_token
def get_zone_favorites():
    """Get zone-to-favorite mapping."""
    if not _bridge:
        return _bridge_unavailable()
    try:
        return jsonify({"ok": True, "zone_favorites": _bridge.get_zone_favorites()})
    except Exception as exc:
        return _handle_bridge_exception("favorites.get", exc)


@musikwolke_bp.route("/favorites/<zone_id>", methods=["POST"])
@require_token
def set_zone_favorite(zone_id: str):
    """Set a preselected favorite for a zone.

    Body: {"favorite_name": "..."}
    """
    if not _bridge:
        return _bridge_unavailable()

    if not _validate_zone_id(zone_id):
        return _json_error("Invalid zone_id format", 400)

    data, err = _require_json_object()
    if err:
        return err

    favorite_name = str(data.get("favorite_name", "")).strip()
    if not favorite_name:
        return _json_error("favorite_name required", 400)

    try:
        _bridge.set_zone_favorite(zone_id, favorite_name)
        return jsonify({"ok": True, "zone_id": zone_id, "favorite_name": favorite_name})
    except Exception as exc:
        return _handle_bridge_exception("favorites.set", exc)


@musikwolke_bp.route("/favorites/<zone_id>", methods=["DELETE"])
@require_token
def delete_zone_favorite(zone_id: str):
    """Remove favorite configuration for a zone."""
    if not _bridge:
        return _bridge_unavailable()

    if not _validate_zone_id(zone_id):
        return _json_error("Invalid zone_id format", 400)

    try:
        _bridge.set_zone_favorite(zone_id, "")  # Clear favorite
        return jsonify({"ok": True, "zone_id": zone_id, "favorite_name": None})
    except Exception as exc:
        return _handle_bridge_exception("favorites.delete", exc)
