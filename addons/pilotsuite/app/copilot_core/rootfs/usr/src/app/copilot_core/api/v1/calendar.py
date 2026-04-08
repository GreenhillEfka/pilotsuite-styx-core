"""Calendar REST API — HA calendar event access for PilotSuite.

Provides endpoints for listing calendar events and injecting them
into the LLM conversation context.
"""

from flask import Blueprint, request, jsonify
import logging
import os
import time
from datetime import datetime, timedelta

import requests as http_requests

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/v1/calendar")

# In-memory cache for calendar events (refreshed on request)
_event_cache: dict[str, list[dict]] = {}  # date_key -> events
_cache_ts: float = 0.0
CACHE_TTL = 300  # 5 min


def _get_ha_headers() -> tuple[str, dict]:
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    return ha_url, headers


def _fetch_calendar_entities() -> list[str]:
    """Discover all calendar.* entities from HA."""
    ha_url, headers = _get_ha_headers()
    try:
        resp = http_requests.get(f"{ha_url}/states", headers=headers, timeout=10)
        if resp.ok:
            return [
                s["entity_id"]
                for s in resp.json()
                if s.get("entity_id", "").startswith("calendar.")
            ]
    except Exception as exc:
        logger.warning("Failed to discover calendars: %s", exc)
    return []


def _fetch_events(start: str, end: str) -> list[dict]:
    """Fetch events from all HA calendars for the given time range."""
    ha_url, headers = _get_ha_headers()
    calendars = _fetch_calendar_entities()
    all_events = []

    for cal_id in calendars:
        try:
            resp = http_requests.get(
                f"{ha_url}/calendars/{cal_id}",
                params={"start": start, "end": end},
                headers=headers,
                timeout=10,
            )
            if resp.ok:
                events = resp.json()
                for ev in events:
                    ev["calendar_entity_id"] = cal_id
                all_events.extend(events)
        except Exception as exc:
            logger.debug("Failed to fetch events from %s: %s", cal_id, exc)

    all_events.sort(key=lambda e: e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")))
    return all_events


@calendar_bp.route("", methods=["GET"])
@require_token
def list_calendars():
    """List all HA calendar entities."""
    calendars = _fetch_calendar_entities()
    return jsonify({"calendars": calendars, "count": len(calendars)})


@calendar_bp.route("/events/today", methods=["GET"])
@require_token
def events_today():
    """Get all calendar events for today."""
    global _event_cache, _cache_ts

    now = datetime.now()
    date_key = now.strftime("%Y-%m-%d")

    if date_key in _event_cache and (time.time() - _cache_ts) < CACHE_TTL:
        return jsonify({"events": _event_cache[date_key], "cached": True})

    start = now.replace(hour=0, minute=0, second=0).isoformat()
    end = (now.replace(hour=0, minute=0, second=0) + timedelta(days=1)).isoformat()
    events = _fetch_events(start, end)

    _event_cache[date_key] = events
    _cache_ts = time.time()

    return jsonify({"events": events, "count": len(events), "cached": False})


@calendar_bp.route("/events/upcoming", methods=["GET"])
@require_token
def events_upcoming():
    """Get upcoming events for the next N days (default 7)."""
    days = min(int(request.args.get("days", 7)), 30)
    now = datetime.now()
    start = now.isoformat()
    end = (now + timedelta(days=days)).isoformat()
    events = _fetch_events(start, end)
    return jsonify({"events": events, "count": len(events), "days": days})


def get_calendar_context_for_llm() -> str:
    """Build calendar context string for LLM system prompt injection."""
    try:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0).isoformat()
        end = (now.replace(hour=0, minute=0, second=0) + timedelta(days=2)).isoformat()
        events = _fetch_events(start, end)
        if not events:
            return ""

        today_str = now.strftime("%d.%m")
        tomorrow_str = (now + timedelta(days=1)).strftime("%d.%m")
        today_events = []
        tomorrow_events = []

        for ev in events:
            ev_start = ev.get("start", {})
            ev_date = ev_start.get("date", ev_start.get("dateTime", ""))[:10]
            ev_summary = ev.get("summary", "?")
            if ev_date == now.strftime("%Y-%m-%d"):
                today_events.append(ev_summary)
            else:
                tomorrow_events.append(ev_summary)

        lines = []
        if today_events:
            lines.append(f"Heute ({today_str}): {', '.join(today_events[:5])}")
        if tomorrow_events:
            lines.append(f"Morgen ({tomorrow_str}): {', '.join(tomorrow_events[:5])}")

        if lines:
            return "Kalender-Termine:\n  " + "\n  ".join(lines)
    except Exception:
        logger.debug("Calendar context failed", exc_info=True)
    return ""
