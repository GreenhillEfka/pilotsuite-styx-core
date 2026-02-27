"""Calendar API — PilotSuite Core.

This API is used by the Core dashboard (ingress UI) to display today's
calendar events without requiring the HACS integration to push anything.

It talks to Home Assistant through the Supervisor proxy:
  http://supervisor/core/api/*

Endpoints (used by dashboard.html):
  GET /api/v1/calendar/events/today
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import requests
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/v1/calendar")

_SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api").rstrip("/")

# Small cache to avoid spamming HA REST on dashboard refreshes.
_CACHE_TTL_S = 60
_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"ts": 0.0, "today": None, "entities": None, "last_error": None}


def _get_token() -> str:
    return (
        os.environ.get("SUPERVISOR_TOKEN", "").strip()
        or os.environ.get("HOME_ASSISTANT_TOKEN", "").strip()
        or os.environ.get("HA_TOKEN", "").strip()
    )


def _ha_headers() -> dict[str, str] | None:
    token = _get_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _ha_get(path: str, *, params: dict[str, Any] | None = None, timeout: int = 12) -> Any:
    headers = _ha_headers()
    if not headers:
        raise RuntimeError("No HA token (SUPERVISOR_TOKEN) available")
    url = f"{_SUPERVISOR_API}{path}"
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    if not resp.ok:
        raise RuntimeError(f"HA GET {path} failed (HTTP {resp.status_code})")
    return resp.json()


def _list_calendar_entities() -> list[dict[str, Any]]:
    """Best-effort: list calendar.* entities from /states."""
    states = _ha_get("/states", timeout=15)
    if not isinstance(states, list):
        return []
    out: list[dict[str, Any]] = []
    for st in states:
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id", "") or "")
        if not eid.startswith("calendar."):
            continue
        attrs = st.get("attributes") or {}
        if not isinstance(attrs, dict):
            attrs = {}
        out.append(
            {
                "entity_id": eid,
                "friendly_name": attrs.get("friendly_name") or eid,
                "state": st.get("state"),
                "supported_features": attrs.get("supported_features"),
            }
        )
    out.sort(key=lambda x: str(x.get("friendly_name") or x.get("entity_id") or ""))
    return out


def _fetch_events(entity_id: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Fetch events for one calendar entity.

    HA REST API (documented) supports:
      GET /api/calendars/<entity_id>?start=<iso>&end=<iso>
    Via Supervisor proxy that becomes:
      GET http://supervisor/core/api/calendars/<entity_id>?start=...&end=...
    """
    # Try the documented query params first.
    params_candidates: list[dict[str, Any]] = [
        {"start": start.isoformat(), "end": end.isoformat()},
        # Some clients use these names; harmless to try.
        {"start_date_time": start.isoformat(), "end_date_time": end.isoformat()},
    ]
    last_err: Exception | None = None
    for params in params_candidates:
        try:
            data = _ha_get(f"/calendars/{entity_id}", params=params, timeout=15)
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict)]
            # Some HA versions wrap.
            events = data.get("events") if isinstance(data, dict) else None
            if isinstance(events, list):
                return [e for e in events if isinstance(e, dict)]
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    if last_err:
        _LOGGER.debug("Calendar fetch failed for %s: %s", entity_id, last_err)
    return []


def _events_today() -> dict[str, Any]:
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    entities = _list_calendar_entities()
    events: list[dict[str, Any]] = []
    for ent in entities[:30]:  # hard cap for safety
        eid = str(ent.get("entity_id") or "")
        if not eid:
            continue
        for ev in _fetch_events(eid, start, end):
            ev_out = dict(ev)
            ev_out.setdefault("calendar_entity_id", eid)
            ev_out.setdefault("calendar_name", ent.get("friendly_name") or eid)
            events.append(ev_out)

    def _sort_key(e: dict[str, Any]) -> str:
        start_raw = e.get("start") or {}
        if isinstance(start_raw, dict):
            return str(start_raw.get("dateTime") or start_raw.get("date") or "")
        return str(start_raw or "")

    events.sort(key=_sort_key)

    return {
        "ok": True,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "calendar_count": len(entities),
        "event_count": len(events),
        "events": events,
    }


@calendar_bp.route("", methods=["GET"])
@require_token
def calendar_root():
    return jsonify({"ok": True, "endpoints": ["/api/v1/calendar/events/today", "/api/v1/calendar/entities"]})


@calendar_bp.route("/entities", methods=["GET"])
@require_token
def calendar_entities():
    try:
        with _cache_lock:
            ts = float(_cache.get("ts", 0.0) or 0.0)
            cached = _cache.get("entities")
            if cached is not None and (time.time() - ts) < _CACHE_TTL_S:
                return jsonify(cached)

        entities = _list_calendar_entities()
        payload = {"ok": True, "count": len(entities), "entities": entities}
        with _cache_lock:
            _cache["ts"] = time.time()
            _cache["entities"] = payload
            _cache["last_error"] = None
        return jsonify(payload)
    except Exception as exc:  # noqa: BLE001
        with _cache_lock:
            _cache["last_error"] = str(exc)
        return jsonify({"ok": False, "error": str(exc), "count": 0, "entities": []}), 503


@calendar_bp.route("/events/today", methods=["GET"])
@require_token
def calendar_events_today():
    # Optional: allow shorter caching during debugging.
    ttl = int(request.args.get("ttl", str(_CACHE_TTL_S)) or _CACHE_TTL_S)
    ttl = max(0, min(ttl, 600))

    try:
        with _cache_lock:
            ts = float(_cache.get("ts", 0.0) or 0.0)
            cached = _cache.get("today")
            if cached is not None and ttl > 0 and (time.time() - ts) < ttl:
                return jsonify(cached)

        payload = _events_today()
        with _cache_lock:
            _cache["ts"] = time.time()
            _cache["today"] = payload
            _cache["last_error"] = None
        return jsonify(payload)
    except Exception as exc:  # noqa: BLE001
        with _cache_lock:
            _cache["last_error"] = str(exc)
        return jsonify({"ok": False, "error": str(exc), "events": []}), 503
