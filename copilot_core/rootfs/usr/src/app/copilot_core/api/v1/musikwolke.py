"""API v1 blueprint for Musikwolke (Music Cloud) control.

Exposes the MusikwolkeBridge for zone-based music control via Sonos.
"""
from __future__ import annotations

import logging
import re

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

musikwolke_bp = Blueprint("musikwolke", __name__, url_prefix="/api/v1/musikwolke")

_bridge = None

_ZONE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")


def _validate_zone_id(zone_id: str) -> bool:
    """Validate zone_id is alphanumeric, max 50 chars."""
    return bool(_ZONE_ID_RE.match(zone_id))


def init_musikwolke_api(bridge) -> None:
    """Wire the MusikwolkeBridge into this blueprint."""
    global _bridge  # noqa: PLW0603
    _bridge = bridge


@musikwolke_bp.route("/status", methods=["GET"])
@require_token
def get_status():
    """Get Musikwolke status (Sonos speakers, active zones, media follow)."""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503
    try:
        return jsonify({"ok": True, **_bridge.get_status()})
    except Exception as exc:
        _LOGGER.exception("Failed to get Musikwolke status")
        return jsonify({"ok": False, "error": str(exc)}), 500


@musikwolke_bp.route("/zone-map", methods=["GET"])
@require_token
def get_zone_map():
    """Get zone-to-speaker mapping."""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503
    return jsonify({"ok": True, "zone_speaker_map": _bridge.get_zone_speaker_map()})


@musikwolke_bp.route("/zone-map", methods=["POST"])
@require_token
def set_zone_speaker():
    """Set a zone-to-speaker mapping.

    Body: {"zone_id": "...", "sonos_room": "..."}
    """
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503

    data = request.get_json(silent=True) or {}
    zone_id = data.get("zone_id", "")
    sonos_room = data.get("sonos_room", "")

    if not zone_id or not sonos_room:
        return jsonify({"ok": False, "error": "zone_id and sonos_room required"}), 400

    if not _validate_zone_id(zone_id):
        return jsonify({"ok": False, "error": "Invalid zone_id format"}), 400

    _bridge.set_zone_speaker(zone_id, sonos_room)
    return jsonify({"ok": True, "zone_id": zone_id, "sonos_room": sonos_room})


@musikwolke_bp.route("/auto-discover", methods=["POST"])
@require_token
def auto_discover():
    """Auto-discover Sonos speakers and map them to zones."""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503

    try:
        mapped = _bridge.auto_discover_mappings()
        return jsonify({
            "ok": True,
            "mapped": mapped,
            "zone_speaker_map": _bridge.get_zone_speaker_map(),
        })
    except Exception as exc:
        _LOGGER.exception("Auto-discover failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@musikwolke_bp.route("/play/<zone_id>", methods=["POST"])
@require_token
def play_zone(zone_id: str):
    """Play music in a zone."""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503

    if not _validate_zone_id(zone_id):
        return jsonify({"ok": False, "error": "Invalid zone_id format"}), 400

    data = request.get_json(silent=True) or {}
    volume = data.get("volume_pct")
    try:
        success = _bridge.play_in_zone(zone_id, volume)
        return jsonify({"ok": success, "zone_id": zone_id, "action": "play"})
    except Exception as exc:
        _LOGGER.exception("Failed to play in zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500


@musikwolke_bp.route("/pause/<zone_id>", methods=["POST"])
@require_token
def pause_zone(zone_id: str):
    """Pause music in a zone."""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503

    if not _validate_zone_id(zone_id):
        return jsonify({"ok": False, "error": "Invalid zone_id format"}), 400

    try:
        success = _bridge.pause_in_zone(zone_id)
        return jsonify({"ok": success, "zone_id": zone_id, "action": "pause"})
    except Exception as exc:
        _LOGGER.exception("Failed to pause in zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500


@musikwolke_bp.route("/volume/<zone_id>", methods=["POST"])
@require_token
def set_volume(zone_id: str):
    """Set volume for a zone. Body: {"volume_pct": 30}"""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503

    if not _validate_zone_id(zone_id):
        return jsonify({"ok": False, "error": "Invalid zone_id format"}), 400

    data = request.get_json(silent=True) or {}
    raw_volume = data.get("volume_pct", 30)
    try:
        volume = int(raw_volume)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "volume_pct must be an integer"}), 400
    if not 0 <= volume <= 100:
        return jsonify({"ok": False, "error": "volume_pct must be between 0 and 100"}), 400

    try:
        success = _bridge.set_zone_volume(zone_id, volume)
        return jsonify({"ok": success, "zone_id": zone_id, "volume_pct": volume})
    except Exception as exc:
        _LOGGER.exception("Failed to set volume in zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500


@musikwolke_bp.route("/create", methods=["POST"])
@require_token
def create_musikwolke():
    """Create a Musikwolke across zones. Body: {"zone_ids": ["z1", "z2", ...]}"""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503

    data = request.get_json(silent=True) or {}
    zone_ids = data.get("zone_ids", [])
    if not isinstance(zone_ids, list) or len(zone_ids) < 2:
        return jsonify({"ok": False, "error": "need at least 2 zones"}), 400
    if not all(_validate_zone_id(z) for z in zone_ids):
        return jsonify({"ok": False, "error": "Invalid zone_id in list"}), 400

    try:
        success = _bridge.create_musikwolke(zone_ids)
        return jsonify({"ok": success, "zone_ids": zone_ids})
    except Exception as exc:
        _LOGGER.exception("Failed to create Musikwolke")
        return jsonify({"ok": False, "error": str(exc)}), 500


@musikwolke_bp.route("/dissolve", methods=["POST"])
@require_token
def dissolve_musikwolke():
    """Dissolve a Musikwolke. Body: {"zone_ids": ["z1", "z2", ...]}"""
    if not _bridge:
        return jsonify({"ok": False, "error": "musikwolke_not_available"}), 503

    data = request.get_json(silent=True) or {}
    zone_ids = data.get("zone_ids", [])

    try:
        success = _bridge.dissolve_musikwolke(zone_ids)
        return jsonify({"ok": success, "zone_ids": zone_ids})
    except Exception as exc:
        _LOGGER.exception("Failed to dissolve Musikwolke")
        return jsonify({"ok": False, "error": str(exc)}), 500
