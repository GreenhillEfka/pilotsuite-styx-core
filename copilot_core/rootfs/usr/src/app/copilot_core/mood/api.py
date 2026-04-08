"""
Mood API endpoints — REST interface for mood scoring.

Endpoints:
    GET  /api/v1/mood                     - Get all zone moods
    GET  /api/v1/mood/{zone_id}           - Get specific zone mood
    GET  /api/v1/mood/summary             - Aggregated mood stats
    POST /api/v1/mood/update-media        - Update moods from MediaContext
    POST /api/v1/mood/update-habitus      - Update moods from Habitus
    GET  /api/v1/mood/{zone_id}/suppress-energy-saving  - Check if energy-saving should be suppressed
"""

from __future__ import annotations

import logging
from flask import Blueprint, request, jsonify, Response

from .service import MoodService
from ..api.security import require_api_key

logger = logging.getLogger(__name__)

# Create blueprint
mood_bp = Blueprint('mood_svc', __name__, url_prefix='/api/v1/mood')

# Global service instance (will be initialized in main.py)
_mood_service: MoodService = None


def init_mood_api(service: MoodService):
    """Initialize the mood API with service instance."""
    global _mood_service
    _mood_service = service


def get_service() -> MoodService:
    """Get or create the global mood service."""
    global _mood_service
    if _mood_service is None:
        _mood_service = MoodService()
    return _mood_service


@mood_bp.route('', methods=['GET'])
@require_api_key
def get_all_moods() -> Response:
    """Get all zone moods."""
    try:
        service = get_service()
        moods = service.get_all_zone_moods()
        
        return jsonify({
            "status": "success",
            "moods": {
                zone_id: mood.to_dict()
                for zone_id, mood in moods.items()
            },
            "zone_count": len(moods)
        })
    
    except Exception as e:
        logger.error(f"Error getting all moods: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@mood_bp.route('/<zone_id>', methods=['GET'])
@require_api_key
def get_zone_mood(zone_id: str) -> Response:
    """Get mood for a specific zone."""
    try:
        service = get_service()
        mood = service.get_zone_mood(zone_id)
        
        if not mood:
            return jsonify({
                "status": "error",
                "error": f"No mood data for zone {zone_id}"
            }), 404
        
        return jsonify({
            "status": "success",
            "mood": mood.to_dict()
        })
    
    except Exception as e:
        logger.error(f"Error getting mood for {zone_id}: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@mood_bp.route('/summary', methods=['GET'])
@require_api_key
def get_mood_summary() -> Response:
    """Get aggregated mood statistics."""
    try:
        service = get_service()
        summary = service.get_summary()
        
        return jsonify({
            "status": "success",
            "summary": summary
        })
    
    except Exception as e:
        logger.error(f"Error getting mood summary: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@mood_bp.route('/update-media', methods=['POST'])
@require_api_key
def update_from_media() -> Response:
    """Update moods based on MediaContext snapshot."""
    try:
        data = request.get_json() or {}
        service = get_service()
        
        # data = MediaContext snapshot
        service.update_from_media_context(data)
        
        return jsonify({
            "status": "success",
            "message": "Moods updated from MediaContext"
        })
    
    except Exception as e:
        logger.error(f"Error updating from media context: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@mood_bp.route('/update-habitus', methods=['POST'])
@require_api_key
def update_from_habitus() -> Response:
    """Update moods based on Habitus context."""
    try:
        data = request.get_json() or {}
        service = get_service()
        
        # data = Habitus context snapshot
        service.update_from_habitus(data)
        
        return jsonify({
            "status": "success",
            "message": "Moods updated from Habitus"
        })
    
    except Exception as e:
        logger.error(f"Error updating from habitus: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@mood_bp.route('/<zone_id>/suppress-energy-saving', methods=['GET'])
@require_api_key
def check_suppress_energy_saving(zone_id: str) -> Response:
    """Check if energy-saving suggestions should be suppressed in this zone."""
    try:
        service = get_service()
        suppress = service.should_suppress_energy_saving(zone_id)
        
        return jsonify({
            "status": "success",
            "zone_id": zone_id,
            "suppress_energy_saving": suppress,
            "reason": "User is likely enjoying entertainment" if suppress else "Suppression not needed"
        })
    
    except Exception as e:
        logger.error(f"Error checking suppress for {zone_id}: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@mood_bp.route('/<zone_id>/relevance/<suggestion_type>', methods=['GET'])
@require_api_key
def get_suggestion_relevance(zone_id: str, suggestion_type: str) -> Response:
    """Get suggestion relevance multiplier for a given zone + suggestion type."""
    try:
        service = get_service()
        multiplier = service.get_suggestion_relevance_multiplier(zone_id, suggestion_type)
        
        return jsonify({
            "status": "success",
            "zone_id": zone_id,
            "suggestion_type": suggestion_type,
            "relevance_multiplier": round(multiplier, 2)
        })
    
    except Exception as e:
        logger.error(f"Error getting relevance for {zone_id}/{suggestion_type}: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
