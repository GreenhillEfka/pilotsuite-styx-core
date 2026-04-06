"""MusicWolke API — REST endpoints for Musikwolke module."""

from __future__ import annotations
import logging
from flask import Blueprint, jsonify, request
from typing import Optional, Any
from copilot_core.api.security import validate_token

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("music_wolke", __name__, url_prefix="/api/v1/music-wolke")
_engine: Optional[Any] = None
_favorites: Optional[Any] = None
_sonos: Optional[Any] = None


def init_music_wolke_api(engine: Any, favorites: Any, sonos: Any) -> None:
    global _engine, _favorites, _sonos
    _engine, _favorites, _sonos = engine, favorites, sonos
    _LOGGER.info("MusicWolke API initialized")


@bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@bp.route("/sessions", methods=["GET"])
def get_sessions():
    if not _engine:
        return jsonify({"error": "not initialized"}), 503
    return jsonify({"ok": True, "sessions": _engine.get_all_sessions()})


@bp.route("/sessions", methods=["POST"])
def start_session():
    if not _engine:
        return jsonify({"error": "not initialized"}), 503
    data = request.get_json() or {}
    zone_id = data.get("zone_id")
    source = data.get("source_entity")
    person_id = data.get("person_id")
    follow = data.get("follow_enabled", True)
    if not zone_id or not source:
        return jsonify({"error": "missing zone_id or source_entity"}), 400
    session_id = _engine.start_session(zone_id, source, "music", person_id, follow)
    return jsonify({"ok": True, "session_id": session_id})


@bp.route("/sessions/<session_id>/transfer", methods=["POST"])
def transfer_session(session_id: str):
    if not _engine:
        return jsonify({"error": "not initialized"}), 503
    data = request.get_json() or {}
    to_zone = data.get("to_zone_id")
    to_source = data.get("to_source_entity")
    if not to_zone or not to_source:
        return jsonify({"error": "missing to_zone_id or to_source"}), 400
    success = _engine.transfer_session(session_id, to_zone, to_source)
    return jsonify({"ok": success, "session_id": session_id})


@bp.route("/sessions/<session_id>/stop", methods=["POST"])
def stop_session(session_id: str):
    if not _engine:
        return jsonify({"error": "not initialized"}), 503
    success = _engine.stop_session(session_id)
    return jsonify({"ok": success, "session_id": session_id})


@bp.route("/zones/<zone_id>/state", methods=["GET"])
def get_zone_state(zone_id: str):
    if not _engine:
        return jsonify({"error": "not initialized"}), 503
    state = _engine.get_zone_state(zone_id)
    return jsonify({"ok": True, "zone_id": zone_id, "state": state.to_dict()})


@bp.route("/zones/<zone_id>/follow", methods=["PUT"])
def set_follow(zone_id: str):
    if not _engine:
        return jsonify({"error": "not initialized"}), 503
    data = request.get_json() or {}
    enabled = data.get("enabled", False)
    success = _engine.set_follow_enabled(zone_id, enabled)
    return jsonify({"ok": success, "zone_id": zone_id, "follow_enabled": enabled})


@bp.route("/zones/<zone_id>/favorites", methods=["GET"])
def get_favorites(zone_id: str):
    if not _favorites:
        return jsonify({"error": "not initialized"}), 503
    sources = _favorites.get_favorites(zone_id)
    return jsonify({"ok": True, "zone_id": zone_id, "favorites": sources})


@bp.route("/zones/<zone_id>/favorites", methods=["POST"])
def set_favorites(zone_id: str):
    if not _favorites:
        return jsonify({"error": "not initialized"}), 503
    data = request.get_json() or {}
    sources = data.get("sources", [])
    success = _favorites.set_favorites(zone_id, sources)
    return jsonify({"ok": success, "zone_id": zone_id})


@bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    if not _engine:
        return jsonify({"error": "not initialized"}), 503
    return jsonify({"ok": True, "dashboard": _engine.get_dashboard()})
