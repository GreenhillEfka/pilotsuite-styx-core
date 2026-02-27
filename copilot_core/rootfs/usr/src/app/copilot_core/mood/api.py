"""Mood API v3.0 — REST endpoints for unified mood system.

Endpoints:
    GET  /api/v1/mood                          → All zone moods
    GET  /api/v1/mood/summary                  → Aggregated stats
    GET  /api/v1/mood/<zone_id>                → Single zone mood
    GET  /api/v1/mood/<zone_id>/history        → Zone mood history
    GET  /api/v1/mood/<zone_id>/distribution   → State distribution
    GET  /api/v1/mood/<zone_id>/suppress-energy-saving
    GET  /api/v1/mood/<zone_id>/relevance/<type>
    GET  /api/v1/mood/<zone_id>/dependencies   → Entity dependencies
    POST /api/v1/mood/update-media             → MediaContext update
    POST /api/v1/mood/update-habitus           → Habitus update
    POST /api/v1/mood/<zone_id>/update         → Partial zone update
"""
from __future__ import annotations

import logging
import threading
from flask import Blueprint, request, jsonify, Response

from .service import MoodService
from ..api.security import require_api_key

logger = logging.getLogger(__name__)

mood_bp = Blueprint("mood_svc", __name__, url_prefix="/api/v1/mood")

_mood_service: MoodService | None = None
_service_lock = threading.Lock()


def init_mood_api(service: MoodService) -> None:
    """Initialize the mood API with service instance."""
    global _mood_service
    _mood_service = service


def get_service() -> MoodService:
    global _mood_service
    if _mood_service is None:
        with _service_lock:
            if _mood_service is None:
                _mood_service = MoodService()
    return _mood_service


@mood_bp.route("", methods=["GET"])
@require_api_key
def get_all_moods() -> Response:
    """Get all zone moods."""
    try:
        service = get_service()
        profiles = service.get_all_zone_profiles()
        return jsonify({
            "status": "success",
            "moods": {zid: p.to_dict() for zid, p in profiles.items()},
            "zone_count": len(profiles),
        })
    except Exception as e:
        logger.exception("Error getting all moods")
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/summary", methods=["GET"])
@require_api_key
def get_mood_summary() -> Response:
    """Get aggregated mood statistics."""
    try:
        service = get_service()
        summary = service.get_summary()
        return jsonify({"status": "success", "summary": summary})
    except Exception as e:
        logger.exception("Error getting mood summary")
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/<zone_id>", methods=["GET"])
@require_api_key
def get_zone_mood(zone_id: str) -> Response:
    """Get mood for a specific zone."""
    try:
        service = get_service()
        profile = service.get_zone_profile(zone_id)
        if not profile:
            return jsonify({"status": "error", "error": f"No mood data for zone {zone_id}"}), 404
        return jsonify({"status": "success", "mood": profile.to_dict()})
    except Exception as e:
        logger.exception("Error getting mood for %s", zone_id)
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/<zone_id>/history", methods=["GET"])
@require_api_key
def get_zone_history(zone_id: str) -> Response:
    """Get mood history for a zone."""
    try:
        hours = request.args.get("hours", 24, type=int)
        limit = request.args.get("limit", 500, type=int)
        service = get_service()
        history = service.get_mood_history(zone_id, hours=hours, limit=limit)
        return jsonify({
            "status": "success",
            "zone_id": zone_id,
            "history": history,
            "count": len(history),
        })
    except Exception as e:
        logger.exception("Error getting history for %s", zone_id)
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/<zone_id>/distribution", methods=["GET"])
@require_api_key
def get_zone_distribution(zone_id: str) -> Response:
    """Get mood state distribution for a zone."""
    try:
        hours = request.args.get("hours", 24, type=int)
        service = get_service()
        dist = service.get_state_distribution(zone_id, hours=hours)
        return jsonify({"status": "success", "zone_id": zone_id, "distribution": dist})
    except Exception as e:
        logger.exception("Error getting distribution for %s", zone_id)
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/<zone_id>/suppress-energy-saving", methods=["GET"])
@require_api_key
def check_suppress_energy_saving(zone_id: str) -> Response:
    """Check if energy-saving should be suppressed in this zone."""
    try:
        service = get_service()
        suppress = service.should_suppress_energy_saving(zone_id)
        return jsonify({
            "status": "success",
            "zone_id": zone_id,
            "suppress_energy_saving": suppress,
            "reason": "Entertainment/comfort active" if suppress else "Normal mode",
        })
    except Exception as e:
        logger.exception("Error checking suppress for %s", zone_id)
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/<zone_id>/relevance/<suggestion_type>", methods=["GET"])
@require_api_key
def get_suggestion_relevance(zone_id: str, suggestion_type: str) -> Response:
    """Get suggestion relevance multiplier for zone + type."""
    try:
        service = get_service()
        multiplier = service.get_suggestion_relevance_multiplier(zone_id, suggestion_type)
        return jsonify({
            "status": "success",
            "zone_id": zone_id,
            "suggestion_type": suggestion_type,
            "relevance_multiplier": round(multiplier, 2),
        })
    except Exception as e:
        logger.exception("Error getting relevance for %s/%s", zone_id, suggestion_type)
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/<zone_id>/dependencies", methods=["GET"])
@require_api_key
def get_zone_dependencies(zone_id: str) -> Response:
    """Get entity dependencies for a zone's mood inference."""
    try:
        from .engine import UnifiedMoodEngine

        engine = None
        try:
            from flask import current_app
            engine = current_app.config.get("MOOD_ENGINE")
        except Exception:
            pass

        deps = engine.get_entity_dependencies(zone_id) if engine else []
        return jsonify({
            "status": "success",
            "zone_id": zone_id,
            "dependencies": [d.to_dict() for d in deps],
            "count": len(deps),
        })
    except Exception as e:
        logger.exception("Error getting dependencies for %s", zone_id)
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/update-media", methods=["POST"])
@require_api_key
def update_from_media() -> Response:
    """Update moods from MediaContext snapshot."""
    try:
        data = request.get_json() or {}
        service = get_service()
        service.update_from_media_context(data)
        return jsonify({"status": "success", "message": "Moods updated from MediaContext"})
    except Exception as e:
        logger.exception("Error updating from media context")
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/update-habitus", methods=["POST"])
@require_api_key
def update_from_habitus() -> Response:
    """Update moods from Habitus context."""
    try:
        data = request.get_json() or {}
        service = get_service()
        service.update_from_habitus(data)
        return jsonify({"status": "success", "message": "Moods updated from Habitus"})
    except Exception as e:
        logger.exception("Error updating from habitus")
        return jsonify({"status": "error", "error": str(e)}), 500


@mood_bp.route("/<zone_id>/update", methods=["POST"])
@require_api_key
def update_zone(zone_id: str) -> Response:
    """Partial update for a zone's mood (from HA integration or neurons)."""
    try:
        data = request.get_json() or {}
        service = get_service()
        service.update_zone_mood(zone_id, data)
        profile = service.get_zone_profile(zone_id)
        return jsonify({
            "status": "success",
            "mood": profile.to_dict() if profile else None,
        })
    except Exception as e:
        logger.exception("Error updating zone %s", zone_id)
        return jsonify({"status": "error", "error": str(e)}), 500
