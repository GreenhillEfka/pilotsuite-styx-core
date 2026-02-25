"""Hauswirtschafts-Dashboard API — v3.2.2.

Aggregates household management data (waste, birthdays, future: calendar)
into a single endpoint for the Haushalt dashboard tab.

GET /api/v1/haushalt/overview
  Returns: {ok, waste: {...}, birthdays: {...}, last_updated}
"""
from __future__ import annotations

import logging
import time
import threading

from flask import Blueprint, jsonify, current_app

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

haushalt_bp = Blueprint("haushalt", __name__, url_prefix="/api/v1/haushalt")

_NETWORK_CACHE_TTL_S = 300
_network_cache_lock = threading.Lock()
_network_cache: dict[str, object] = {
    "ts": 0.0,
    "news": {"items": [], "error": "not_initialized"},
    "warnings": {"warnings": [], "error": "not_initialized"},
}


def _first_weather_snapshot() -> dict:
    """Return best-effort weather snapshot from HA weather entities."""
    try:
        from homeassistant.core import HomeAssistant

        hass = HomeAssistant.get()
        if not hass:
            return {}
        weather_entities = [st for st in hass.states.async_all() if st.domain == "weather"]
        if not weather_entities:
            return {}
        state = weather_entities[0]
        forecast = state.attributes.get("forecast") or []
        return {
            "entity_id": state.entity_id,
            "friendly_name": state.attributes.get("friendly_name"),
            "state": state.state,
            "temperature": state.attributes.get("temperature"),
            "humidity": state.attributes.get("humidity"),
            "wind_speed": state.attributes.get("wind_speed"),
            "forecast": forecast[:5] if isinstance(forecast, list) else [],
        }
    except Exception:
        return {}


def _cached_news_and_warnings(web_search_service) -> tuple[dict, dict]:
    """Read news/warnings with short-lived cache to protect waitress queue depth."""
    if not web_search_service:
        return {"items": [], "error": "not_initialized"}, {"warnings": [], "error": "not_initialized"}

    now = time.time()
    cached_ts = float(_network_cache.get("ts", 0.0) or 0.0)
    if now - cached_ts < _NETWORK_CACHE_TTL_S:
        return (
            dict(_network_cache.get("news", {"items": []})),
            dict(_network_cache.get("warnings", {"warnings": []})),
        )

    with _network_cache_lock:
        cached_ts = float(_network_cache.get("ts", 0.0) or 0.0)
        if now - cached_ts < _NETWORK_CACHE_TTL_S:
            return (
                dict(_network_cache.get("news", {"items": []})),
                dict(_network_cache.get("warnings", {"warnings": []})),
            )

        news_data = {"items": [], "error": "not_initialized"}
        warnings_data = {"warnings": [], "error": "not_initialized"}
        try:
            news_data = web_search_service.get_news(max_items=8)
        except Exception as exc:
            _LOGGER.debug("Could not load household news: %s", exc)
            news_data = {"items": [], "error": str(exc)}
        try:
            warnings_data = web_search_service.get_regional_warnings()
        except Exception as exc:
            _LOGGER.debug("Could not load household warnings: %s", exc)
            warnings_data = {"warnings": [], "error": str(exc)}

        _network_cache["ts"] = now
        _network_cache["news"] = news_data
        _network_cache["warnings"] = warnings_data
        return dict(news_data), dict(warnings_data)


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
    web_search_service = services.get("web_search_service")
    system_health_service = services.get("system_health_service")
    zone_engine = services.get("hub_zones")

    waste_data = waste_service.get_status() if waste_service else {"ok": False, "error": "not initialized"}
    birthday_data = birthday_service.get_status() if birthday_service else {"ok": False, "error": "not initialized"}
    weather_data = _first_weather_snapshot()
    news_data, warnings_data = _cached_news_and_warnings(web_search_service)

    system_health = {"status": "unknown"}
    if system_health_service:
        try:
            health_raw = system_health_service.get_full_health(force_refresh=False)
            if isinstance(health_raw, dict):
                system_health = {
                    "status": health_raw.get("status", "unknown"),
                    "subsystems": health_raw.get("subsystems", {}),
                }
        except Exception as exc:
            _LOGGER.debug("Could not load system health: %s", exc)

    zone_summary = {"total_zones": 0, "active_zones": 0, "total_rooms": 0, "total_entities": 0}
    if zone_engine:
        try:
            overview = zone_engine.get_overview()
            zone_summary = {
                "total_zones": int(getattr(overview, "total_zones", 0)),
                "active_zones": int(getattr(overview, "active_zones", 0)),
                "total_rooms": int(getattr(overview, "total_rooms", 0)),
                "total_entities": int(getattr(overview, "total_entities", 0)),
            }
        except Exception as exc:
            _LOGGER.debug("Could not load zone summary: %s", exc)

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
        "weather": weather_data,
        "news": news_data,
        "warnings": warnings_data,
        "house_status": {
            "system_health": system_health,
            "zones": zone_summary,
        },
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
