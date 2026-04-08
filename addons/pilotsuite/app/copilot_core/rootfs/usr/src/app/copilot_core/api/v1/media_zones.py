"""
Media Zone Manager + Proactive Context Engine API.

Endpoints for managing media zones, playback control, Musikwolke
(smart audio follow), and proactive context-driven suggestions.

Blueprint prefix: /api/v1/media

All modifying endpoints require a valid auth token (Bearer or X-Auth-Token).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

media_zones_bp = Blueprint(
    "media_zones", __name__, url_prefix="/api/v1/media"
)

# Module-level service references, set by init_media_zones_api()
_media_mgr: Optional[Any] = None
_proactive_engine: Optional[Any] = None


def init_media_zones_api(media_mgr, proactive_engine) -> None:
    """Wire MediaZoneManager and ProactiveContextEngine into the blueprint.

    Called from ``core_setup.register_blueprints()`` or ``init_services()``.

    Parameters
    ----------
    media_mgr:
        A ``copilot_core.media_zone_manager.MediaZoneManager`` instance.
    proactive_engine:
        A ``copilot_core.proactive_engine.ProactiveContextEngine`` instance.
    """
    global _media_mgr, _proactive_engine
    _media_mgr = media_mgr
    _proactive_engine = proactive_engine
    _LOGGER.info("Media Zones API initialized")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _require_media_mgr():
    """Return the MediaZoneManager or a 503 error tuple."""
    if _media_mgr is None:
        return None, (jsonify({
            "ok": False,
            "error": "MediaZoneManager not initialized",
        }), 503)
    return _media_mgr, None


def _require_proactive_engine():
    """Return the ProactiveContextEngine or a 503 error tuple."""
    if _proactive_engine is None:
        return None, (jsonify({
            "ok": False,
            "error": "ProactiveContextEngine not initialized",
        }), 503)
    return _proactive_engine, None


# ===================================================================
# Zone Assignment
# ===================================================================

@media_zones_bp.route("/zones", methods=["GET"])
def get_all_zones():
    """Return all zone-player assignments.

    Response::

        {
            "ok": true,
            "zones": { "living_room": [...], "bedroom": [...] }
        }
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        assignments = mgr.get_all_assignments()
    except Exception as exc:
        _LOGGER.exception("Failed to get all zone assignments")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "zones": assignments})


@media_zones_bp.route("/zones/<zone_id>", methods=["GET"])
def get_zone_players(zone_id: str):
    """Return players assigned to a specific zone.

    Response::

        {
            "ok": true,
            "zone_id": "living_room",
            "players": [...]
        }
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        players = mgr.get_zone_players(zone_id)
    except Exception as exc:
        _LOGGER.exception("Failed to get players for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "zone_id": zone_id, "players": players})


@media_zones_bp.route("/zones/<zone_id>/assign", methods=["POST"])
@require_token
def assign_player(zone_id: str):
    """Assign a media player entity to a zone.

    Request body::

        {
            "entity_id": "media_player.living_room_speaker",
            "role": "primary"    // optional
        }

    Response::

        {"ok": true, "zone_id": "living_room", "entity_id": "media_player.living_room_speaker"}
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    entity_id = data.get("entity_id", "").strip()

    if not entity_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'entity_id'",
        }), 400

    role = data.get("role")

    try:
        kwargs: dict[str, Any] = {"zone_id": zone_id, "entity_id": entity_id}
        if role is not None:
            kwargs["role"] = role
        mgr.assign_player(**kwargs)
    except Exception as exc:
        _LOGGER.exception("Failed to assign player %s to zone %s", entity_id, zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "entity_id": entity_id,
    }), 201


@media_zones_bp.route("/zones/<zone_id>/<entity_id>", methods=["DELETE"])
@require_token
def unassign_player(zone_id: str, entity_id: str):
    """Remove a media player from a zone.

    Response::

        {"ok": true, "zone_id": "living_room", "entity_id": "media_player.living_room_speaker"}
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        mgr.unassign_player(zone_id=zone_id, entity_id=entity_id)
    except Exception as exc:
        _LOGGER.exception("Failed to unassign player %s from zone %s", entity_id, zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "entity_id": entity_id,
    })


# ===================================================================
# Playback Control
# ===================================================================

@media_zones_bp.route("/zones/<zone_id>/play", methods=["POST"])
@require_token
def play_zone(zone_id: str):
    """Resume playback for all players in a zone.

    Response::

        {"ok": true, "zone_id": "living_room", "action": "play"}
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        mgr.play_zone(zone_id)
    except Exception as exc:
        _LOGGER.exception("Failed to play zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "zone_id": zone_id, "action": "play"})


@media_zones_bp.route("/zones/<zone_id>/pause", methods=["POST"])
@require_token
def pause_zone(zone_id: str):
    """Pause playback for all players in a zone.

    Response::

        {"ok": true, "zone_id": "living_room", "action": "pause"}
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        mgr.pause_zone(zone_id)
    except Exception as exc:
        _LOGGER.exception("Failed to pause zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "zone_id": zone_id, "action": "pause"})


@media_zones_bp.route("/zones/<zone_id>/volume", methods=["POST"])
@require_token
def set_zone_volume(zone_id: str):
    """Set the volume for all players in a zone.

    Request body::

        {"volume": 0.65}    // 0.0 - 1.0

    Response::

        {"ok": true, "zone_id": "living_room", "volume": 0.65}
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    volume = data.get("volume")

    if volume is None:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'volume'",
        }), 400

    try:
        volume = float(volume)
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "error": "'volume' must be a number between 0.0 and 1.0",
        }), 400

    if not 0.0 <= volume <= 1.0:
        return jsonify({
            "ok": False,
            "error": "'volume' must be between 0.0 and 1.0",
        }), 400

    try:
        mgr.set_zone_volume(zone_id, volume)
    except Exception as exc:
        _LOGGER.exception("Failed to set volume for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "zone_id": zone_id, "volume": volume})


@media_zones_bp.route("/zones/<zone_id>/play-media", methods=["POST"])
@require_token
def play_media_in_zone(zone_id: str):
    """Play specific media content in a zone.

    Request body::

        {
            "media_content_id": "spotify:track:abc123",
            "media_content_type": "music"    // optional
        }

    Response::

        {
            "ok": true,
            "zone_id": "living_room",
            "media_content_id": "spotify:track:abc123"
        }
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    media_content_id = data.get("media_content_id", "").strip()

    if not media_content_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'media_content_id'",
        }), 400

    media_content_type = data.get("media_content_type")

    try:
        kwargs: dict[str, Any] = {
            "zone_id": zone_id,
            "media_content_id": media_content_id,
        }
        if media_content_type is not None:
            kwargs["media_content_type"] = media_content_type
        mgr.play_media_in_zone(**kwargs)
    except Exception as exc:
        _LOGGER.exception("Failed to play media in zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    result: dict[str, Any] = {
        "ok": True,
        "zone_id": zone_id,
        "media_content_id": media_content_id,
    }
    if media_content_type is not None:
        result["media_content_type"] = media_content_type
    return jsonify(result)


@media_zones_bp.route("/zones/<zone_id>/state", methods=["GET"])
def get_zone_media_state(zone_id: str):
    """Return the current media state for a zone.

    Response::

        {
            "ok": true,
            "zone_id": "living_room",
            "state": { ... }
        }
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        state = mgr.get_zone_media_state(zone_id)
    except Exception as exc:
        _LOGGER.exception("Failed to get media state for zone %s", zone_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "zone_id": zone_id, "state": state})


# ===================================================================
# Musikwolke (Smart Audio Follow)
# ===================================================================

@media_zones_bp.route("/musikwolke/start", methods=["POST"])
@require_token
def start_musikwolke():
    """Start a Musikwolke session -- audio follows a person between zones.

    Request body::

        {
            "person_id": "person.alice",
            "source_zone": "living_room"
        }

    Response::

        {
            "ok": true,
            "session_id": "mw_abc123",
            "person_id": "person.alice",
            "source_zone": "living_room"
        }
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    person_id = data.get("person_id", "").strip()
    source_zone = data.get("source_zone", "").strip()

    if not person_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'person_id'",
        }), 400

    if not source_zone:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'source_zone'",
        }), 400

    try:
        result = mgr.start_musikwolke(person_id=person_id, source_zone=source_zone)
    except Exception as exc:
        _LOGGER.exception("Failed to start Musikwolke session")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "session_id": result.get("session_id") if isinstance(result, dict) else result,
        "person_id": person_id,
        "source_zone": source_zone,
    }), 201


@media_zones_bp.route("/musikwolke/<session_id>/update", methods=["POST"])
@require_token
def update_musikwolke(session_id: str):
    """Notify that the tracked person entered a new zone.

    Request body::

        {"entered_zone": "bedroom"}

    Response::

        {"ok": true, "session_id": "mw_abc123", "entered_zone": "bedroom"}
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    entered_zone = data.get("entered_zone", "").strip()

    if not entered_zone:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'entered_zone'",
        }), 400

    try:
        mgr.update_musikwolke(session_id=session_id, entered_zone=entered_zone)
    except Exception as exc:
        _LOGGER.exception("Failed to update Musikwolke session %s", session_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "entered_zone": entered_zone,
    })


@media_zones_bp.route("/musikwolke/<session_id>/stop", methods=["POST"])
@require_token
def stop_musikwolke(session_id: str):
    """Stop a Musikwolke session.

    Response::

        {"ok": true, "session_id": "mw_abc123", "stopped": true}
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        mgr.stop_musikwolke(session_id=session_id)
    except Exception as exc:
        _LOGGER.exception("Failed to stop Musikwolke session %s", session_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "stopped": True,
    })


@media_zones_bp.route("/musikwolke", methods=["GET"])
def list_musikwolke_sessions():
    """List all active Musikwolke sessions.

    Response::

        {
            "ok": true,
            "sessions": [...]
        }
    """
    mgr, err = _require_media_mgr()
    if err:
        return err

    try:
        sessions = mgr.get_musikwolke_sessions()
    except Exception as exc:
        _LOGGER.exception("Failed to list Musikwolke sessions")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "sessions": sessions})


# ===================================================================
# Proactive Suggestions
# ===================================================================

@media_zones_bp.route("/proactive/zone-entry", methods=["POST"])
@require_token
def proactive_zone_entry():
    """Trigger proactive suggestions when a person enters a zone.

    Request body::

        {
            "person_id": "person.alice",
            "zone_id": "living_room",
            "context": { ... }    // optional extra context
        }

    Response::

        {
            "ok": true,
            "person_id": "person.alice",
            "zone_id": "living_room",
            "suggestions": [...]
        }
    """
    engine, err = _require_proactive_engine()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    person_id = data.get("person_id", "").strip()
    zone_id = data.get("zone_id", "").strip()

    if not person_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'person_id'",
        }), 400

    if not zone_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'zone_id'",
        }), 400

    context = data.get("context")

    suggestions = []
    try:
        kwargs: dict[str, Any] = {
            "person_id": person_id,
            "zone_id": zone_id,
        }
        if context is not None:
            kwargs["context"] = context
        suggestions = engine.on_zone_entry(**kwargs)
    except Exception as exc:
        _LOGGER.exception("Failed to process zone entry for %s in %s", person_id, zone_id)

    # Also update active Musikwolke sessions for this person
    musikwolke_updated = False
    if _media_mgr is not None:
        try:
            sessions = _media_mgr.get_musikwolke_sessions()
            for sess in (sessions if isinstance(sessions, list) else []):
                sess_person = sess.get("person_id", "") if isinstance(sess, dict) else ""
                sess_id = sess.get("session_id", "") if isinstance(sess, dict) else ""
                if sess_person == person_id and sess_id:
                    _media_mgr.update_musikwolke(session_id=sess_id, entered_zone=zone_id)
                    musikwolke_updated = True
                    _LOGGER.info("Musikwolke session %s: %s -> %s", sess_id, person_id, zone_id)
        except Exception:
            _LOGGER.debug("Failed to update Musikwolke on zone entry", exc_info=True)

    return jsonify({
        "ok": True,
        "person_id": person_id,
        "zone_id": zone_id,
        "suggestions": suggestions,
        "musikwolke_updated": musikwolke_updated,
    })


@media_zones_bp.route("/proactive/deliver", methods=["POST"])
@require_token
def proactive_deliver():
    """Deliver a proactive suggestion to the user.

    Request body::

        {
            "suggestion": { ... },
            "method": "notification"    // optional delivery method
        }

    Response::

        {"ok": true, "delivered": true}
    """
    engine, err = _require_proactive_engine()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    suggestion = data.get("suggestion")

    if not suggestion:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'suggestion'",
        }), 400

    method = data.get("method")

    try:
        kwargs: dict[str, Any] = {"suggestion": suggestion}
        if method is not None:
            kwargs["method"] = method
        result = engine.deliver_suggestion(**kwargs)
    except Exception as exc:
        _LOGGER.exception("Failed to deliver proactive suggestion")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "delivered": True,
        "result": result,
    })


@media_zones_bp.route("/proactive/dismiss", methods=["POST"])
@require_token
def proactive_dismiss():
    """Dismiss a specific suggestion type for a person.

    Request body::

        {
            "person_id": "person.alice",
            "suggestion_type": "music_recommendation"
        }

    Response::

        {"ok": true, "person_id": "person.alice", "suggestion_type": "music_recommendation"}
    """
    engine, err = _require_proactive_engine()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    person_id = data.get("person_id", "").strip()
    suggestion_type = data.get("suggestion_type", "").strip()

    if not person_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'person_id'",
        }), 400

    if not suggestion_type:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'suggestion_type'",
        }), 400

    try:
        engine.dismiss_type(person_id=person_id, suggestion_type=suggestion_type)
    except Exception as exc:
        _LOGGER.exception("Failed to dismiss suggestion type %s for %s", suggestion_type, person_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "person_id": person_id,
        "suggestion_type": suggestion_type,
    })


@media_zones_bp.route("/proactive/reset-dismissals", methods=["POST"])
@require_token
def proactive_reset_dismissals():
    """Reset all dismissals for a person.

    Request body::

        {"person_id": "person.alice"}

    Response::

        {"ok": true, "person_id": "person.alice", "reset": true}
    """
    engine, err = _require_proactive_engine()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    person_id = data.get("person_id", "").strip()

    if not person_id:
        return jsonify({
            "ok": False,
            "error": "Missing required field 'person_id'",
        }), 400

    try:
        engine.reset_dismissals(person_id=person_id)
    except Exception as exc:
        _LOGGER.exception("Failed to reset dismissals for %s", person_id)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "person_id": person_id,
        "reset": True,
    })
