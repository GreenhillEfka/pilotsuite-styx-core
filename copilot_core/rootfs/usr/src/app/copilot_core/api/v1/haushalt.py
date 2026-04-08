"""Hauswirtschafts-Dashboard API — v3.2.2.

Aggregates household management data (waste, birthdays, future: calendar)
into a single endpoint for the Haushalt dashboard tab.

GET /api/v1/haushalt/overview
  Returns: {ok, waste: {...}, birthdays: {...}, last_updated}
"""
from __future__ import annotations

import logging
import time

from flask import Blueprint, jsonify, current_app

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

haushalt_bp = Blueprint("haushalt", __name__, url_prefix="/api/v1/haushalt")


@haushalt_bp.route("/overview", methods=["GET"])
@require_token
def haushalt_overview():
    """Aggregate waste + birthday status for the Haushalt dashboard."""
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
    except Exception:
        services = {}

    waste_service = services.get("waste_service")
    birthday_service = services.get("birthday_service")

    waste_data = waste_service.get_status() if waste_service else {"ok": False, "error": "not initialized"}
    birthday_data = birthday_service.get_status() if birthday_service else {"ok": False, "error": "not initialized"}

    # Derive urgency flags
    waste_today = waste_data.get("today", []) if isinstance(waste_data, dict) else []
    waste_tomorrow = waste_data.get("tomorrow", []) if isinstance(waste_data, dict) else []
    birthday_today = birthday_data.get("today", []) if isinstance(birthday_data, dict) else []
    birthday_upcoming = birthday_data.get("upcoming", []) if isinstance(birthday_data, dict) else []

    # Next 7-day birthday count
    upcoming_7 = [b for b in birthday_upcoming if b.get("days_until", 99) <= 7]

    return jsonify({
        "ok": True,
        "last_updated": time.time(),
        "alerts": {
            "waste_today": len(waste_today) > 0,
            "waste_tomorrow": len(waste_tomorrow) > 0,
            "birthday_today": len(birthday_today) > 0,
            "upcoming_birthdays_7d": len(upcoming_7),
        },
        "waste": waste_data,
        "birthdays": birthday_data,
    })


@haushalt_bp.route("/remind/waste", methods=["POST"])
@require_token
def haushalt_remind_waste():
    """Trigger immediate waste reminder from Haushalt dashboard."""
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
        waste_service = services.get("waste_service")
        if not waste_service:
            return jsonify({"ok": False, "error": "WasteCollectionService not available"}), 503
        status = waste_service.get_status()
        today = status.get("today", [])
        tomorrow = status.get("tomorrow", [])
        if today:
            message = f"Heute wird abgeholt: {', '.join(today)}."
        elif tomorrow:
            message = f"Morgen wird abgeholt: {', '.join(tomorrow)}. Bitte Tonnen rausstellen!"
        else:
            return jsonify({"ok": True, "message": "Keine Abfuhr in Sicht."})
        return jsonify(waste_service.deliver_reminder(message))
    except Exception as exc:
        _LOGGER.warning("Haushalt waste remind error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@haushalt_bp.route("/remind/birthday", methods=["POST"])
@require_token
def haushalt_remind_birthday():
    """Trigger immediate birthday reminder from Haushalt dashboard."""
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
        birthday_service = services.get("birthday_service")
        if not birthday_service:
            return jsonify({"ok": False, "error": "BirthdayService not available"}), 503
        status = birthday_service.get_status()
        today = status.get("today", [])
        if not today:
            return jsonify({"ok": True, "message": "Keine Geburtstage heute."})
        names = [b.get("name", "?") + (f" (wird {b.get('age', '?')})" if b.get("age") else "") for b in today]
        message = f"Heute hat Geburtstag: {', '.join(names)}. Herzlichen Glückwunsch!"
        return jsonify(birthday_service.deliver_reminder(message))
    except Exception as exc:
        _LOGGER.warning("Haushalt birthday remind error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500
