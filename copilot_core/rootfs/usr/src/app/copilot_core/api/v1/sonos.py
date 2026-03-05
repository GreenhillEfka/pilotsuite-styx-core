"""Sonos REST API Blueprint — native Sonos-Steuerung via node-sonos-http-api.

Prefix: /api/v1/sonos
~37 Endpoints: System, Per-Room, Global, Intelligence
"""

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.api.rate_limit import rate_limit

_LOGGER = logging.getLogger(__name__)

sonos_bp = Blueprint("sonos", __name__, url_prefix="/api/v1/sonos")

_client: Optional[Any] = None
_intel: Optional[Any] = None


def init_sonos_api(client, intelligence) -> None:
    """Wire Sonos services into API blueprint."""
    global _client, _intel
    _client = client
    _intel = intelligence


def _require_client():
    if _client is None:
        return None, (jsonify({"ok": False, "error": "Sonos client not initialized"}), 503)
    return _client, None


def _require_intel():
    if _intel is None:
        return None, (jsonify({"ok": False, "error": "Sonos intelligence not initialized"}), 503)
    return _intel, None


# ── System ──────────────────────────────────────────────────────────────────

@sonos_bp.route("/health", methods=["GET"])
def sonos_health():
    client, err = _require_client()
    if err:
        return err
    healthy = client.is_healthy()
    return jsonify({"ok": True, "healthy": healthy})


@sonos_bp.route("/zones", methods=["GET"])
def sonos_zones():
    client, err = _require_client()
    if err:
        return err
    zones = client.get_zones()
    return jsonify({"ok": True, "zones": zones or []})


@sonos_bp.route("/rooms", methods=["GET"])
def sonos_rooms():
    client, err = _require_client()
    if err:
        return err
    rooms = client.get_rooms()
    return jsonify({"ok": True, "rooms": rooms})


# ── Per-Room: State ─────────────────────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/state", methods=["GET"])
def sonos_room_state(room: str):
    client, err = _require_client()
    if err:
        return err
    state = client.get_state(room)
    if state is None:
        return jsonify({"ok": False, "error": f"Could not get state for {room}"}), 404
    return jsonify({"ok": True, "room": room, "state": state})


# ── Per-Room: Playback Control ──────────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/play", methods=["POST"])
@require_token
def sonos_play(room: str):
    client, err = _require_client()
    if err:
        return err
    client.play(room)
    return jsonify({"ok": True, "room": room, "action": "play"})


@sonos_bp.route("/rooms/<room>/pause", methods=["POST"])
@require_token
def sonos_pause(room: str):
    client, err = _require_client()
    if err:
        return err
    client.pause(room)
    return jsonify({"ok": True, "room": room, "action": "pause"})


@sonos_bp.route("/rooms/<room>/stop", methods=["POST"])
@require_token
def sonos_stop(room: str):
    client, err = _require_client()
    if err:
        return err
    client.stop(room)
    return jsonify({"ok": True, "room": room, "action": "stop"})


@sonos_bp.route("/rooms/<room>/toggle", methods=["POST"])
@require_token
def sonos_toggle(room: str):
    client, err = _require_client()
    if err:
        return err
    client.playpause(room)
    return jsonify({"ok": True, "room": room, "action": "toggle"})


@sonos_bp.route("/rooms/<room>/next", methods=["POST"])
@require_token
def sonos_next(room: str):
    client, err = _require_client()
    if err:
        return err
    client.next(room)
    return jsonify({"ok": True, "room": room, "action": "next"})


@sonos_bp.route("/rooms/<room>/previous", methods=["POST"])
@require_token
def sonos_previous(room: str):
    client, err = _require_client()
    if err:
        return err
    client.previous(room)
    return jsonify({"ok": True, "room": room, "action": "previous"})


# ── Per-Room: Volume ────────────────────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/volume", methods=["POST"])
@require_token
def sonos_volume(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    vol = data.get("volume")
    if vol is None:
        return jsonify({"ok": False, "error": "Missing 'volume'"}), 400
    # Volume-Ceiling anwenden wenn Intelligence verfuegbar
    if _intel:
        vol = _intel.apply_volume_ceiling("", int(vol))
    client.set_volume(room, int(vol))
    return jsonify({"ok": True, "room": room, "volume": int(vol)})


@sonos_bp.route("/rooms/<room>/volume/adjust", methods=["POST"])
@require_token
def sonos_volume_adjust(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    delta = data.get("delta", 0)
    client.adjust_volume(room, int(delta))
    return jsonify({"ok": True, "room": room, "delta": int(delta)})


@sonos_bp.route("/rooms/<room>/mute", methods=["POST"])
@require_token
def sonos_mute(room: str):
    client, err = _require_client()
    if err:
        return err
    action = (request.get_json(silent=True) or {}).get("action", "toggle")
    if action == "on":
        client.mute(room)
    elif action == "off":
        client.unmute(room)
    else:
        client.toggle_mute(room)
    return jsonify({"ok": True, "room": room, "mute_action": action})


# ── Per-Room: Favorites / Playlists ────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/favorites", methods=["GET"])
def sonos_favorites(room: str):
    client, err = _require_client()
    if err:
        return err
    favs = client.get_favorites(room)
    return jsonify({"ok": True, "room": room, "favorites": favs or []})


@sonos_bp.route("/rooms/<room>/favorite", methods=["POST"])
@require_token
@rate_limit(requests=20)
def sonos_play_favorite(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    if not name:
        return jsonify({"ok": False, "error": "Missing 'name'"}), 400
    client.play_favorite(room, name)
    return jsonify({"ok": True, "room": room, "favorite": name})


@sonos_bp.route("/rooms/<room>/playlists", methods=["GET"])
def sonos_playlists(room: str):
    # node-sonos-http-api hat keinen dedizierten Playlists-Endpoint,
    # Playlists sind Teil der Favorites
    client, err = _require_client()
    if err:
        return err
    favs = client.get_favorites(room)
    return jsonify({"ok": True, "room": room, "playlists": favs or []})


@sonos_bp.route("/rooms/<room>/playlist", methods=["POST"])
@require_token
@rate_limit(requests=20)
def sonos_play_playlist(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    if not name:
        return jsonify({"ok": False, "error": "Missing 'name'"}), 400
    client.play_playlist(room, name)
    return jsonify({"ok": True, "room": room, "playlist": name})


# ── Per-Room: Queue ─────────────────────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/queue", methods=["GET"])
def sonos_queue(room: str):
    client, err = _require_client()
    if err:
        return err
    queue = client.get_queue(room)
    return jsonify({"ok": True, "room": room, "queue": queue or []})


@sonos_bp.route("/rooms/<room>/queue/clear", methods=["POST"])
@require_token
def sonos_clear_queue(room: str):
    client, err = _require_client()
    if err:
        return err
    client.clear_queue(room)
    return jsonify({"ok": True, "room": room, "action": "queue_cleared"})


# ── Per-Room: Grouping ──────────────────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/join", methods=["POST"])
@require_token
def sonos_join(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    coordinator = data.get("coordinator", "")
    if not coordinator:
        return jsonify({"ok": False, "error": "Missing 'coordinator'"}), 400
    client.join(room, coordinator)
    return jsonify({"ok": True, "room": room, "joined": coordinator})


@sonos_bp.route("/rooms/<room>/leave", methods=["POST"])
@require_token
def sonos_leave(room: str):
    client, err = _require_client()
    if err:
        return err
    client.leave(room)
    return jsonify({"ok": True, "room": room, "action": "left_group"})


# ── Per-Room: TTS ───────────────────────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/say", methods=["POST"])
@require_token
@rate_limit(requests=10)
def sonos_say(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"ok": False, "error": "Missing 'text'"}), 400
    volume = data.get("volume")
    language = data.get("language", "de-de")
    client.say(room, text, volume=volume, language=language)
    return jsonify({"ok": True, "room": room, "action": "say", "text": text})


# ── Per-Room: Sleep / Shuffle ───────────────────────────────────────────────

@sonos_bp.route("/rooms/<room>/sleep", methods=["POST"])
@require_token
def sonos_sleep(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    seconds = data.get("seconds", 900)
    client.set_sleep(room, int(seconds))
    return jsonify({"ok": True, "room": room, "sleep_seconds": int(seconds)})


@sonos_bp.route("/rooms/<room>/shuffle", methods=["POST"])
@require_token
def sonos_shuffle(room: str):
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    on = data.get("on", True)
    client.set_shuffle(room, bool(on))
    return jsonify({"ok": True, "room": room, "shuffle": bool(on)})


# ── Global ──────────────────────────────────────────────────────────────────

@sonos_bp.route("/sayall", methods=["POST"])
@require_token
@rate_limit(requests=5)
def sonos_say_all():
    client, err = _require_client()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"ok": False, "error": "Missing 'text'"}), 400
    volume = data.get("volume")
    language = data.get("language", "de-de")
    client.say_all(text, volume=volume, language=language)
    return jsonify({"ok": True, "action": "say_all", "text": text})


@sonos_bp.route("/pauseall", methods=["POST"])
@require_token
def sonos_pause_all():
    client, err = _require_client()
    if err:
        return err
    client.pause_all()
    return jsonify({"ok": True, "action": "pause_all"})


@sonos_bp.route("/resumeall", methods=["POST"])
@require_token
def sonos_resume_all():
    client, err = _require_client()
    if err:
        return err
    client.resume_all()
    return jsonify({"ok": True, "action": "resume_all"})


# ── Intelligence: Volume Profiles ───────────────────────────────────────────

@sonos_bp.route("/volume-profiles", methods=["GET"])
def sonos_volume_profiles():
    intel, err = _require_intel()
    if err:
        return err
    return jsonify({"ok": True, "profiles": intel.get_all_volume_profiles()})


@sonos_bp.route("/volume-profiles/<name>", methods=["PUT"])
@require_token
def sonos_update_volume_profile(name: str):
    intel, err = _require_intel()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    ok = intel.update_volume_profile(name, **data)
    if not ok:
        return jsonify({"ok": False, "error": f"Profile '{name}' not found"}), 404
    return jsonify({"ok": True, "updated": name})


# ── Intelligence: Presets ───────────────────────────────────────────────────

@sonos_bp.route("/presets", methods=["GET"])
def sonos_list_presets():
    intel, err = _require_intel()
    if err:
        return err
    return jsonify({"ok": True, "presets": intel.list_presets()})


@sonos_bp.route("/presets", methods=["POST"])
@require_token
def sonos_create_preset():
    intel, err = _require_intel()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    from copilot_core.sonos.models import SonosPreset
    try:
        preset = SonosPreset(
            preset_id=data.get("preset_id", ""),
            label=data.get("label", ""),
            players=data.get("players", []),
            favorite=data.get("favorite", ""),
            playlist=data.get("playlist", ""),
            shuffle=data.get("shuffle", False),
            zone_id=data.get("zone_id", ""),
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not preset.preset_id:
        return jsonify({"ok": False, "error": "Missing 'preset_id'"}), 400
    ok = intel.save_preset(preset)
    return jsonify({"ok": ok, "preset_id": preset.preset_id})


@sonos_bp.route("/presets/<preset_id>", methods=["GET"])
def sonos_get_preset(preset_id: str):
    intel, err = _require_intel()
    if err:
        return err
    preset = intel.get_preset(preset_id)
    if not preset:
        return jsonify({"ok": False, "error": "Preset not found"}), 404
    return jsonify({
        "ok": True,
        "preset": {
            "preset_id": preset.preset_id,
            "label": preset.label,
            "players": preset.players,
            "favorite": preset.favorite,
            "playlist": preset.playlist,
            "shuffle": preset.shuffle,
            "zone_id": preset.zone_id,
            "state": preset.state,
        },
    })


@sonos_bp.route("/presets/<preset_id>", methods=["DELETE"])
@require_token
def sonos_delete_preset(preset_id: str):
    intel, err = _require_intel()
    if err:
        return err
    ok = intel.delete_preset(preset_id)
    if not ok:
        return jsonify({"ok": False, "error": "Preset not found"}), 404
    return jsonify({"ok": True, "deleted": preset_id})


@sonos_bp.route("/presets/<preset_id>/apply", methods=["POST"])
@require_token
def sonos_apply_preset(preset_id: str):
    intel, err = _require_intel()
    if err:
        return err
    ok = intel.apply_preset(preset_id)
    if not ok:
        return jsonify({"ok": False, "error": "Preset not found or apply failed"}), 404
    return jsonify({"ok": True, "applied": preset_id})


# ── Intelligence: Zone Registry ─────────────────────────────────────────────

@sonos_bp.route("/intelligence/zones", methods=["GET"])
def sonos_intel_zones():
    intel, err = _require_intel()
    if err:
        return err
    return jsonify({"ok": True, "zones": intel.get_all_zones()})


@sonos_bp.route("/intelligence/zones", methods=["POST"])
@require_token
def sonos_register_zone():
    intel, err = _require_intel()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    from copilot_core.sonos.models import SonosZone
    zone_id = data.get("zone_id", "")
    primary = data.get("primary_room", "")
    if not zone_id or not primary:
        return jsonify({"ok": False, "error": "Missing 'zone_id' or 'primary_room'"}), 400
    zone = SonosZone(
        zone_id=zone_id,
        primary_room=primary,
        secondary_rooms=data.get("secondary_rooms", []),
    )
    intel.register_zone(zone)
    return jsonify({"ok": True, "registered": zone_id})


# ── Intelligence: Fallback ──────────────────────────────────────────────────

@sonos_bp.route("/intelligence/zones/<zone_id>/fallback", methods=["GET"])
def sonos_get_fallback(zone_id: str):
    intel, err = _require_intel()
    if err:
        return err
    fb = intel.get_fallback(zone_id)
    if not fb:
        return jsonify({"ok": True, "fallback": None})
    return jsonify({
        "ok": True,
        "fallback": {
            "zone_id": fb.zone_id,
            "fallback_type": fb.fallback_type,
            "favorite_name": fb.favorite_name,
            "playlist_name": fb.playlist_name,
            "uri": fb.uri,
            "volume_pct": fb.volume_pct,
            "shuffle": fb.shuffle,
        },
    })


@sonos_bp.route("/intelligence/zones/<zone_id>/fallback", methods=["POST"])
@require_token
def sonos_set_fallback(zone_id: str):
    intel, err = _require_intel()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    from copilot_core.sonos.models import FallbackConfig
    fb = FallbackConfig(
        zone_id=zone_id,
        fallback_type=data.get("fallback_type", "favorite"),
        favorite_name=data.get("favorite_name", ""),
        playlist_name=data.get("playlist_name", ""),
        uri=data.get("uri", ""),
        volume_pct=data.get("volume_pct", 25),
        shuffle=data.get("shuffle", True),
    )
    intel.set_fallback(zone_id, fb)
    return jsonify({"ok": True, "zone_id": zone_id})


# ── Intelligence: Presence ──────────────────────────────────────────────────

@sonos_bp.route("/intelligence/presence", methods=["POST"])
@require_token
def sonos_presence():
    intel, err = _require_intel()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    zone_id = data.get("zone_id", "")
    person_id = data.get("person_id", "")
    if not zone_id:
        return jsonify({"ok": False, "error": "Missing 'zone_id'"}), 400
    result = intel.on_zone_presence(zone_id, person_id)
    return jsonify({"ok": True, **result})
