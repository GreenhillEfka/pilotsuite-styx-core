"""Sonos Direct API — jishi/node-sonos-http-api Steuerung.

Direkte Sonos-Steuerung ohne HA Supervisor-Umweg.
Nutzt SonosCloudClient (hub/sonos_client.py) → jishi API (Port 5005).

Blueprint prefix: /api/v1/sonos
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.api.rate_limit import rate_limit

_LOGGER = logging.getLogger(__name__)

sonos_bp = Blueprint("sonos", __name__, url_prefix="/api/v1/sonos")


def _get_sonos():
    """Hole SonosCloudClient aus Services."""
    services = current_app.config.get("COPILOT_SERVICES", {})
    client = services.get("sonos_client")
    if client is None:
        return None, (jsonify({"ok": False, "error": "Sonos client not initialized"}), 503)
    return client, None


# ── Discovery / Status ─────────────────────────────────────────

@sonos_bp.route("/zones", methods=["GET"])
@require_token
@rate_limit(requests=30)
def get_zones():
    """Sonos-Topologie: alle Zonen und Speaker."""
    client, err = _get_sonos()
    if err:
        return err

    zones = client.discover_zones()
    speakers = client.get_speakers()
    return jsonify({
        "ok": True,
        "total_speakers": len(speakers),
        "zones": zones,
    })


@sonos_bp.route("/speakers", methods=["GET"])
@require_token
@rate_limit(requests=30)
def get_speakers():
    """Alle bekannten Speaker (aus Cache)."""
    client, err = _get_sonos()
    if err:
        return err

    speakers = client.get_speakers()
    return jsonify({
        "ok": True,
        "speakers": [
            {
                "room_name": s.room_name,
                "uuid": s.uuid,
                "state": s.state,
                "volume": s.volume,
                "muted": s.muted,
                "track": {
                    "title": s.track_title,
                    "artist": s.track_artist,
                    "album": s.track_album,
                },
                "is_coordinator": s.is_coordinator,
                "group_members": s.group_members,
            }
            for s in speakers
        ],
    })


@sonos_bp.route("/summary", methods=["GET"])
@require_token
@rate_limit(requests=30)
def get_summary():
    """Dashboard-Summary aller Sonos-Speaker."""
    client, err = _get_sonos()
    if err:
        return err

    return jsonify({"ok": True, **client.get_summary()})


@sonos_bp.route("/health", methods=["GET"])
def health_check():
    """Prüfe ob jishi API erreichbar ist."""
    client, err = _get_sonos()
    if err:
        return err

    healthy = client.health_check()
    return jsonify({"ok": healthy, "service": "node-sonos-http-api"}), 200 if healthy else 503


# ── Playback Control ───────────────────────────────────────────

@sonos_bp.route("/play", methods=["POST"])
@require_token
@rate_limit(requests=60)
def play():
    """Wiedergabe starten. Body: {"room": "Wohnzimmer"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    if not room:
        return jsonify({"ok": False, "error": "Missing 'room'"}), 400

    ok = client.play(room)
    return jsonify({"ok": ok, "room": room, "action": "play"})


@sonos_bp.route("/pause", methods=["POST"])
@require_token
@rate_limit(requests=60)
def pause():
    """Wiedergabe pausieren. Body: {"room": "Wohnzimmer"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    if not room:
        return jsonify({"ok": False, "error": "Missing 'room'"}), 400

    ok = client.pause(room)
    return jsonify({"ok": ok, "room": room, "action": "pause"})


@sonos_bp.route("/next", methods=["POST"])
@require_token
@rate_limit(requests=60)
def next_track():
    """Naechster Track. Body: {"room": "Wohnzimmer"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    if not room:
        return jsonify({"ok": False, "error": "Missing 'room'"}), 400

    ok = client.next_track(room)
    return jsonify({"ok": ok, "room": room, "action": "next"})


@sonos_bp.route("/previous", methods=["POST"])
@require_token
@rate_limit(requests=60)
def previous_track():
    """Vorheriger Track. Body: {"room": "Wohnzimmer"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    if not room:
        return jsonify({"ok": False, "error": "Missing 'room'"}), 400

    ok = client.previous_track(room)
    return jsonify({"ok": ok, "room": room, "action": "previous"})


# ── Volume Control ─────────────────────────────────────────────

@sonos_bp.route("/volume", methods=["POST"])
@require_token
@rate_limit(requests=60)
def set_volume():
    """Lautstaerke setzen. Body: {"room": "Wohnzimmer", "volume": 30}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    volume = data.get("volume")

    if not room:
        return jsonify({"ok": False, "error": "Missing 'room'"}), 400
    if volume is None or not isinstance(volume, (int, float)):
        return jsonify({"ok": False, "error": "Missing or invalid 'volume'"}), 400

    ok = client.set_volume(room, int(volume))
    return jsonify({"ok": ok, "room": room, "volume": int(volume)})


@sonos_bp.route("/mute", methods=["POST"])
@require_token
@rate_limit(requests=60)
def set_mute():
    """Mute/Unmute. Body: {"room": "Wohnzimmer", "muted": true}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    muted = data.get("muted", True)

    if not room:
        return jsonify({"ok": False, "error": "Missing 'room'"}), 400

    ok = client.set_mute(room, bool(muted))
    return jsonify({"ok": ok, "room": room, "muted": bool(muted)})


# ── Favorites / Playlists ──────────────────────────────────────

@sonos_bp.route("/favorites", methods=["GET"])
@require_token
@rate_limit(requests=30)
def get_favorites():
    """Sonos-Favoriten auflisten."""
    client, err = _get_sonos()
    if err:
        return err

    return jsonify({"ok": True, "favorites": client.get_favorites()})


@sonos_bp.route("/favorite/play", methods=["POST"])
@require_token
@rate_limit(requests=30)
def play_favorite():
    """Favorit abspielen. Body: {"room": "Wohnzimmer", "name": "WDR 2"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    name = data.get("name", "").strip()

    if not room or not name:
        return jsonify({"ok": False, "error": "Missing 'room' or 'name'"}), 400

    ok = client.play_favorite(room, name)
    return jsonify({"ok": ok, "room": room, "favorite": name})


@sonos_bp.route("/playlists", methods=["GET"])
@require_token
@rate_limit(requests=30)
def get_playlists():
    """Sonos-Playlists auflisten."""
    client, err = _get_sonos()
    if err:
        return err

    return jsonify({"ok": True, "playlists": client.get_playlists()})


# ── TTS / Say ──────────────────────────────────────────────────

@sonos_bp.route("/say", methods=["POST"])
@require_token
@rate_limit(requests=20)
def say():
    """TTS Ansage. Body: {"room": "Wohnzimmer", "text": "Hallo!", "language": "de-de", "volume": 40}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    text = data.get("text", "").strip()
    language = data.get("language", "de-de")
    volume = data.get("volume")

    if not room or not text:
        return jsonify({"ok": False, "error": "Missing 'room' or 'text'"}), 400
    if len(text) > 500:
        return jsonify({"ok": False, "error": "Text too long (max 500 chars)"}), 400

    ok = client.say(room, text, language=language, volume=volume)
    return jsonify({"ok": ok, "room": room, "action": "say"})


@sonos_bp.route("/say-all", methods=["POST"])
@require_token
@rate_limit(requests=10)
def say_all():
    """TTS auf allen Speakern. Body: {"text": "Achtung!", "language": "de-de"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    language = data.get("language", "de-de")
    volume = data.get("volume")

    if not text:
        return jsonify({"ok": False, "error": "Missing 'text'"}), 400
    if len(text) > 500:
        return jsonify({"ok": False, "error": "Text too long (max 500 chars)"}), 400

    ok = client.say_all(text, language=language, volume=volume)
    return jsonify({"ok": ok, "action": "say-all"})


# ── Musikwolke (Speaker Grouping) ──────────────────────────────

@sonos_bp.route("/musikwolke/create", methods=["POST"])
@require_token
@rate_limit(requests=10)
def create_musikwolke():
    """Musikwolke erstellen. Body: {"rooms": ["Wohnzimmer", "Kueche", "Schlafzimmer"]}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    rooms = data.get("rooms", [])

    if not isinstance(rooms, list) or len(rooms) < 2:
        return jsonify({"ok": False, "error": "Need at least 2 rooms"}), 400

    ok = client.create_musikwolke(rooms)
    return jsonify({"ok": ok, "rooms": rooms, "action": "musikwolke-create"})


@sonos_bp.route("/musikwolke/dissolve", methods=["POST"])
@require_token
@rate_limit(requests=10)
def dissolve_musikwolke():
    """Musikwolke aufloesen. Body: {"rooms": ["Wohnzimmer", "Kueche"]}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    rooms = data.get("rooms", [])

    if not isinstance(rooms, list) or len(rooms) < 1:
        return jsonify({"ok": False, "error": "Need at least 1 room"}), 400

    ok = client.dissolve_musikwolke(rooms)
    return jsonify({"ok": ok, "rooms": rooms, "action": "musikwolke-dissolve"})


@sonos_bp.route("/musikwolke/follow", methods=["POST"])
@require_token
@rate_limit(requests=30)
def follow_user():
    """Musikwolke folgt User. Body: {"user_room": "Kueche", "previous_room": "Wohnzimmer", "musikwolke_rooms": ["Wohnzimmer", "Kueche"]}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    user_room = data.get("user_room", "").strip()
    previous_room = data.get("previous_room")
    musikwolke_rooms = data.get("musikwolke_rooms", [])

    if not user_room:
        return jsonify({"ok": False, "error": "Missing 'user_room'"}), 400

    ok = client.follow_user(
        user_room=user_room,
        previous_room=previous_room,
        musikwolke_rooms=musikwolke_rooms,
    )
    return jsonify({"ok": ok, "user_room": user_room, "action": "follow"})


@sonos_bp.route("/join", methods=["POST"])
@require_token
@rate_limit(requests=30)
def join():
    """Room einer Gruppe joinen. Body: {"room": "Kueche", "target": "Wohnzimmer"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()
    target = data.get("target", "").strip()

    if not room or not target:
        return jsonify({"ok": False, "error": "Missing 'room' or 'target'"}), 400

    ok = client.join(room, target)
    return jsonify({"ok": ok, "room": room, "target": target, "action": "join"})


@sonos_bp.route("/leave", methods=["POST"])
@require_token
@rate_limit(requests=30)
def leave():
    """Room aus Gruppe entfernen. Body: {"room": "Kueche"}"""
    client, err = _get_sonos()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    room = data.get("room", "").strip()

    if not room:
        return jsonify({"ok": False, "error": "Missing 'room'"}), 400

    ok = client.leave(room)
    return jsonify({"ok": ok, "room": room, "action": "leave"})
