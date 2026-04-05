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


def _load_services() -> dict:
    try:
        services = current_app.config.get("COPILOT_SERVICES", {})
    except Exception:
        return {}
    return services if isinstance(services, dict) else {}


def _ensure_status_dict(status: object, service_name: str) -> dict:
    if not isinstance(status, dict):
        raise TypeError(f"{service_name} status must be an object")
    return status


def _status_list(status: dict, key: str) -> list:
    value = status.get(key, [])
    return value if isinstance(value, list) else []


@haushalt_bp.route("/overview", methods=["GET"])
@require_token
def haushalt_overview():
    """Aggregate waste + birthday status for the Haushalt dashboard."""
    try:
        services = _load_services()
        waste_service = services.get("waste_service")
        birthday_service = services.get("birthday_service")

        waste_data = (
            _ensure_status_dict(waste_service.get_status(), "WasteCollectionService")
            if waste_service
            else {"ok": False, "error": "not initialized"}
        )
        birthday_data = (
            _ensure_status_dict(birthday_service.get_status(), "BirthdayService")
            if birthday_service
            else {"ok": False, "error": "not initialized"}
        )

        # Derive urgency flags
        waste_today = _status_list(waste_data, "today")
        waste_tomorrow = _status_list(waste_data, "tomorrow")
        birthday_today = _status_list(birthday_data, "today")
        birthday_upcoming = _status_list(birthday_data, "upcoming")

        # Next 7-day birthday count
        upcoming_7 = [
            birthday
            for birthday in birthday_upcoming
            if isinstance(birthday, dict) and birthday.get("days_until", 99) <= 7
        ]

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
    except Exception as exc:
        _LOGGER.warning("Haushalt overview error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@haushalt_bp.route("/remind/waste", methods=["POST"])
@require_token
def haushalt_remind_waste():
    """Trigger immediate waste reminder from Haushalt dashboard."""
    try:
        services = _load_services()
        waste_service = services.get("waste_service")
        if not waste_service:
            return jsonify({"ok": False, "error": "WasteCollectionService not available"}), 503
        status = _ensure_status_dict(waste_service.get_status(), "WasteCollectionService")
        today = _status_list(status, "today")
        tomorrow = _status_list(status, "tomorrow")
        if today:
            message = f"Heute wird abgeholt: {', '.join(str(item) for item in today)}."
        elif tomorrow:
            message = f"Morgen wird abgeholt: {', '.join(str(item) for item in tomorrow)}. Bitte Tonnen rausstellen!"
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
        services = _load_services()
        birthday_service = services.get("birthday_service")
        if not birthday_service:
            return jsonify({"ok": False, "error": "BirthdayService not available"}), 503
        status = _ensure_status_dict(birthday_service.get_status(), "BirthdayService")
        today = _status_list(status, "today")
        if not today:
            return jsonify({"ok": True, "message": "Keine Geburtstage heute."})

        names = []
        for birthday in today:
            if isinstance(birthday, dict):
                name = str(birthday.get("name", "?"))
                age = birthday.get("age")
                names.append(f"{name} (wird {age})" if age else name)
            else:
                names.append(str(birthday))

        message = f"Heute hat Geburtstag: {', '.join(names)}. Herzlichen Glückwunsch!"
        return jsonify(birthday_service.deliver_reminder(message))
    except Exception as exc:
        _LOGGER.warning("Haushalt birthday remind error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500
