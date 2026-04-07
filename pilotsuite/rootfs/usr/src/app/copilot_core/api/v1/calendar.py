"""Calendar API v1 for PilotSuite Core.

Provides unified calendar endpoints for:
- ICS/iCal files and URLs
- Google Calendar
- CalDAV servers (Nextcloud, ownCloud, iCloud)

Endpoints:
- GET /api/v1/calendar/events — Get calendar events
- POST /api/v1/calendar/sync — Sync calendar sources
- GET /api/v1/calendar/upcoming — Get upcoming events
- GET /api/v1/calendar/sources — List calendar sources
- POST /api/v1/calendar/sources — Add calendar source
- DELETE /api/v1/calendar/sources/<source_id> — Remove calendar source
- GET /api/v1/calendar/presence — Get presence prediction from calendar
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from copilot_core.calendar import (
    get_calendar_manager,
    CalendarSource,
    CalendarSourceConfig,
    CalendarSyncStatus,
)

logger = logging.getLogger(__name__)

bp = Blueprint("calendar", __name__, url_prefix="/api/v1/calendar")

# Global reference to calendar manager (set during app initialization)
_calendar_manager = None


def set_calendar_manager(manager) -> None:
    """Set the calendar manager instance for API access."""
    global _calendar_manager
    _calendar_manager = manager
    logger.info("Calendar API: Manager set")


def get_calendar_manager_api():
    """Get the calendar manager instance."""
    global _calendar_manager
    if _calendar_manager is None:
        _calendar_manager = get_calendar_manager()
    return _calendar_manager


# =============================================================================
# GET /api/v1/calendar/events — Get calendar events
# =============================================================================

@bp.get("/events")
def get_calendar_events():
    """
    Get calendar events from all sources.
    
    Query params:
        source_id (optional): Filter to specific source
        start (optional): Start of time range (ISO format)
        end (optional): End of time range (ISO format)
        limit (optional): Maximum events to return (default: 100)
    
    Returns:
        JSON response with events list
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        # Parse query params
        source_id = request.args.get("source_id")
        limit = int(request.args.get("limit", "100"))
        
        # Parse date range
        start = None
        end = None
        
        start_str = request.args.get("start")
        if start_str:
            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        end_str = request.args.get("end")
        if end_str:
            try:
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        events = manager.get_events(
            source_id=source_id,
            start=start,
            end=end,
            limit=limit,
        )
        
        return jsonify({
            "ok": True,
            "events": events,
            "count": len(events),
        })
        
    except Exception as exc:
        logger.error("Failed to get calendar events: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# POST /api/v1/calendar/sync — Sync calendar sources
# =============================================================================

@bp.post("/sync")
def sync_calendar():
    """
    Sync calendar sources.
    
    Body (optional):
        source_id (optional): Sync specific source (None for all)
        force (optional): Force refresh even if recently synced
    
    Returns:
        JSON response with sync results
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        data = request.get_json() or {}
        source_id = data.get("source_id")
        force = data.get("force", False)
        
        if source_id:
            # Sync specific source
            count = manager.sync_source(source_id)
            return jsonify({
                "ok": True,
                "source_id": source_id,
                "events_synced": count,
            })
        else:
            # Sync all sources
            results = manager.sync_all()
            return jsonify({
                "ok": True,
                "sources_synced": results,
                "total_events": sum(results.values()),
            })
        
    except Exception as exc:
        logger.error("Failed to sync calendar: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# GET /api/v1/calendar/upcoming — Get upcoming events
# =============================================================================

@bp.get("/upcoming")
def get_upcoming_events():
    """
    Get upcoming calendar events.
    
    Query params:
        hours (optional): Hours to look ahead (default: 24)
        source_id (optional): Filter to specific source
        limit (optional): Maximum events to return (default: 50)
    
    Returns:
        JSON response with upcoming events
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        # Parse query params
        hours = int(request.args.get("hours", "24"))
        source_id = request.args.get("source_id")
        limit = int(request.args.get("limit", "50"))
        
        # Validate hours
        hours = max(1, min(hours, 720))  # 1 hour to 30 days
        
        events = manager.get_upcoming_events(
            hours_ahead=hours,
            source_id=source_id,
            limit=limit,
        )
        
        return jsonify({
            "ok": True,
            "events": events,
            "count": len(events),
            "hours_ahead": hours,
        })
        
    except Exception as exc:
        logger.error("Failed to get upcoming events: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# GET /api/v1/calendar/sources — List calendar sources
# =============================================================================

@bp.get("/sources")
def list_calendar_sources():
    """
    List all calendar sources.
    
    Returns:
        JSON response with sources list
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        sources = manager.list_sources()
        
        return jsonify({
            "ok": True,
            "sources": sources,
            "count": len(sources),
        })
        
    except Exception as exc:
        logger.error("Failed to list calendar sources: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# POST /api/v1/calendar/sources — Add calendar source
# =============================================================================

@bp.post("/sources")
def add_calendar_source():
    """
    Add a new calendar source.
    
    Body (required fields vary by source_type):
        source_id (required): Unique identifier for this source
        source_type (required): Type of source (ics, google, caldav, ha)
        name (required): Display name
        enabled (optional): Enable source (default: true)
        
        For ICS:
            ics_path (optional): Local file path
            ics_url (optional): Remote URL
            
        For Google:
            google_credentials_path (optional): OAuth2 credentials JSON path
            google_token_path (optional): Token storage path
            google_service_account_path (optional): Service account JSON path
            google_calendar_ids (optional): List of calendar IDs to sync
            
        For CalDAV:
            caldav_url (required): CalDAV server URL
            caldav_username (optional): Username
            caldav_password (optional): Password
            caldav_calendar_url (optional): Specific calendar URL
            caldav_calendar_name (optional): Calendar name
            caldav_ssl_verify (optional): Verify SSL (default: true)
    
    Returns:
        JSON response with source info
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        data = request.get_json() or {}
        
        # Validate required fields
        required = ["source_id", "source_type", "name"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                "ok": False,
                "error": f"Missing required fields: {', '.join(missing)}",
            }), 400
        
        # Validate source type
        source_type_str = data.get("source_type")
        try:
            source_type = CalendarSource(source_type_str)
        except ValueError:
            return jsonify({
                "ok": False,
                "error": f"Invalid source_type. Must be one of: {[s.value for s in CalendarSource]}",
            }), 400
        
        # Build config
        config = CalendarSourceConfig(
            source_id=data["source_id"],
            source_type=source_type,
            name=data["name"],
            enabled=data.get("enabled", True),
            ics_path=data.get("ics_path"),
            ics_url=data.get("ics_url"),
            google_credentials_path=data.get("google_credentials_path"),
            google_token_path=data.get("google_token_path"),
            google_service_account_path=data.get("google_service_account_path"),
            google_calendar_ids=data.get("google_calendar_ids", []),
            caldav_url=data.get("caldav_url"),
            caldav_username=data.get("caldav_username"),
            caldav_password=data.get("caldav_password"),
            caldav_calendar_url=data.get("caldav_calendar_url"),
            caldav_calendar_name=data.get("caldav_calendar_name"),
            caldav_ssl_verify=data.get("caldav_ssl_verify", True),
            sync_interval_minutes=data.get("sync_interval_minutes", 15),
        )
        
        # Add source
        if not manager.add_source(config):
            return jsonify({
                "ok": False,
                "error": f"Source {data['source_id']} already exists",
            }), 409
        
        # Initial sync
        count = manager.sync_source(data["source_id"])
        
        return jsonify({
            "ok": True,
            "source": config.to_dict(),
            "events_synced": count,
        }), 201
        
    except Exception as exc:
        logger.error("Failed to add calendar source: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# DELETE /api/v1/calendar/sources/<source_id> — Remove calendar source
# =============================================================================

@bp.delete("/sources/<source_id>")
def remove_calendar_source(source_id: str):
    """
    Remove a calendar source.
    
    Args:
        source_id: Source identifier to remove
    
    Returns:
        JSON response with removal status
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        if not manager.remove_source(source_id):
            return jsonify({
                "ok": False,
                "error": f"Source {source_id} not found",
            }), 404
        
        return jsonify({
            "ok": True,
            "source_id": source_id,
        })
        
    except Exception as exc:
        logger.error("Failed to remove calendar source: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# POST /api/v1/calendar/sources/<source_id>/enable — Enable source
# =============================================================================

@bp.post("/sources/<source_id>/enable")
def enable_calendar_source(source_id: str):
    """Enable a calendar source."""
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        if not manager.enable_source(source_id):
            return jsonify({
                "ok": False,
                "error": f"Source {source_id} not found",
            }), 404
        
        # Sync after enabling
        count = manager.sync_source(source_id)
        
        return jsonify({
            "ok": True,
            "source_id": source_id,
            "enabled": True,
            "events_synced": count,
        })
        
    except Exception as exc:
        logger.error("Failed to enable calendar source: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# POST /api/v1/calendar/sources/<source_id>/disable — Disable source
# =============================================================================

@bp.post("/sources/<source_id>/disable")
def disable_calendar_source(source_id: str):
    """Disable a calendar source."""
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        if not manager.disable_source(source_id):
            return jsonify({
                "ok": False,
                "error": f"Source {source_id} not found",
            }), 404
        
        return jsonify({
            "ok": True,
            "source_id": source_id,
            "enabled": False,
        })
        
    except Exception as exc:
        logger.error("Failed to disable calendar source: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# GET /api/v1/calendar/presence — Get presence prediction
# =============================================================================

@bp.get("/presence")
def get_presence_prediction():
    """
    Get presence prediction based on calendar events.
    
    Query params:
        hours (optional): Hours to predict (default: 4)
    
    Returns:
        JSON response with presence prediction
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        hours = int(request.args.get("hours", "4"))
        hours = max(1, min(hours, 24))
        
        prediction = manager.get_presence_prediction(hours_ahead=hours)
        
        return jsonify({
            "ok": True,
            "prediction": prediction,
        })
        
    except Exception as exc:
        logger.error("Failed to get presence prediction: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# =============================================================================
# GET /api/v1/calendar/summary — Get calendar summary
# =============================================================================

@bp.get("/summary")
def get_calendar_summary():
    """
    Get calendar system summary.
    
    Returns:
        JSON response with summary stats
    """
    try:
        manager = get_calendar_manager_api()
        if not manager:
            return jsonify({
                "ok": False,
                "error": "Calendar manager not available",
            }), 503
        
        summary = manager.get_calendar_summary()
        
        return jsonify({
            "ok": True,
            "summary": summary,
        })
        
    except Exception as exc:
        logger.error("Failed to get calendar summary: %s", exc)
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# Backwards compatibility alias
calendar_bp = bp
