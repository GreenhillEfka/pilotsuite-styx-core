"""
REST API for Waste Collection + Birthday Reminders (v3.2.0).

Endpoints:
  POST /api/v1/waste/event        -- Receive waste event from HACS integration
  POST /api/v1/waste/collections  -- Update full waste collection schedule
  GET  /api/v1/waste/status       -- Get current waste status
  POST /api/v1/waste/remind       -- Trigger immediate waste reminder (TTS + notification)
  POST /api/v1/birthday/update    -- Update birthday list from HACS integration
  GET  /api/v1/birthday/status    -- Get current birthday status
  POST /api/v1/birthday/remind    -- Trigger immediate birthday reminder
"""

from __future__ import annotations

import logging
from flask import Blueprint, request, jsonify

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

reminders_bp = Blueprint("reminders", __name__, url_prefix="/api/v1")

# Module-level references (set via init_reminders_api)
_waste_service = None
_birthday_service = None


def init_reminders_api(waste_service=None, birthday_service=None):
    """Set service instances for the reminders API."""
    global _waste_service, _birthday_service
    _waste_service = waste_service
    _birthday_service = birthday_service
    _LOGGER.info(
        "Reminders API initialized (waste=%s, birthday=%s)",
        waste_service is not None,
        birthday_service is not None,
    )


# ------------------------------------------------------------------
# Waste Collection Endpoints
# ------------------------------------------------------------------

@reminders_bp.route("/waste/event", methods=["POST"])
@require_token
def waste_event():
    """Receive a waste event from the HACS integration."""
    if not _waste_service:
        return jsonify({"ok": False, "error": "WasteCollectionService not available"}), 503
    data = request.get_json(silent=True) or {}
    result = _waste_service.update_from_ha(data)
    return jsonify(result)


@reminders_bp.route("/waste/collections", methods=["POST"])
@require_token
def waste_collections_update():
    """Update full waste collection schedule."""
    if not _waste_service:
        return jsonify({"ok": False, "error": "WasteCollectionService not available"}), 503
    data = request.get_json(silent=True) or {}
    collections = data.get("collections", [])
    result = _waste_service.update_collections(collections)
    return jsonify(result)


@reminders_bp.route("/waste/status", methods=["GET"])
@require_token
def waste_status():
    """Get current waste collection status."""
    if not _waste_service:
        return jsonify({"ok": False, "error": "WasteCollectionService not available"}), 503
    return jsonify(_waste_service.get_status())


@reminders_bp.route("/waste/remind", methods=["POST"])
@require_token
def waste_remind():
    """Trigger an immediate waste reminder."""
    if not _waste_service:
        return jsonify({"ok": False, "error": "WasteCollectionService not available"}), 503
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    tts_entity = data.get("tts_entity", "")
    if not message:
        status = _waste_service.get_status()
        today = status.get("today", [])
        tomorrow = status.get("tomorrow", [])
        if today:
            message = f"Heute wird abgeholt: {', '.join(today)}."
        elif tomorrow:
            message = f"Morgen wird abgeholt: {', '.join(tomorrow)}. Bitte Tonnen rausstellen!"
        else:
            return jsonify({"ok": True, "message": "Keine Abfuhr in Sicht."})
    result = _waste_service.deliver_reminder(message, tts_entity)
    return jsonify(result)


# ------------------------------------------------------------------
# Birthday Endpoints
# ------------------------------------------------------------------

@reminders_bp.route("/birthday/update", methods=["POST"])
@require_token
def birthday_update():
    """Update birthday list from HACS integration."""
    if not _birthday_service:
        return jsonify({"ok": False, "error": "BirthdayService not available"}), 503
    data = request.get_json(silent=True) or {}
    birthdays = data.get("birthdays", [])
    result = _birthday_service.update_birthdays(birthdays)
    return jsonify(result)


@reminders_bp.route("/birthday/status", methods=["GET"])
@require_token
def birthday_status():
    """Get current birthday status."""
    if not _birthday_service:
        return jsonify({"ok": False, "error": "BirthdayService not available"}), 503
    return jsonify(_birthday_service.get_status())


@reminders_bp.route("/birthday/remind", methods=["POST"])
@require_token
def birthday_remind():
    """Trigger an immediate birthday reminder."""
    if not _birthday_service:
        return jsonify({"ok": False, "error": "BirthdayService not available"}), 503
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    tts_entity = data.get("tts_entity", "")
    if not message:
        status = _birthday_service.get_status()
        today = status.get("today", [])
        if today:
            names = [b.get("name", "?") for b in today]
            message = f"Heute hat Geburtstag: {', '.join(names)}. Herzlichen Glückwunsch!"
        else:
            return jsonify({"ok": True, "message": "Keine Geburtstage heute."})
    result = _birthday_service.deliver_reminder(message, tts_entity)
    return jsonify(result)
