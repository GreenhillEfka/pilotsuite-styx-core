"""Presence Tracking API — v3.3.0.

Tracks who is home and where, receives updates from HACS integration.

GET  /api/v1/presence/status  — current presence map
POST /api/v1/presence/update  — receive presence update from HACS
GET  /api/v1/presence/history — recent arrivals/departures

Blueprint prefix: /api/v1/presence

All modifying endpoints require a valid auth token (Bearer or X-Auth-Token).
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

presence_bp = Blueprint("presence", __name__, url_prefix="/api/v1/presence")

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
# Keyed by person_id -> dict with current state.
# Thread-safe for single-writer (POST /update) via Flask/GIL; reads are
# snapshot-safe because dict reads in CPython are atomic.
_presence_map: dict[str, dict[str, Any]] = {}

# Ring buffer of recent state-change events (newest first).
_presence_history: deque[dict[str, Any]] = deque(maxlen=200)


# ===================================================================
# Endpoints
# ===================================================================

@presence_bp.route("/status", methods=["GET"])
@require_token
def presence_status():
    """Return current presence map.

    Response::

        {
            "ok": true,
            "persons_home": [...],
            "persons_away": [...],
            "total_home": 2,
            "total_tracked": 4,
            "last_updated": 1700000000.0
        }
    """
    persons_home = [
        p for p in _presence_map.values()
        if p.get("state") not in ("not_home", "unknown")
        and p.get("state")
    ]
    persons_away = [
        p for p in _presence_map.values()
        if p.get("state") in ("not_home", "unknown")
    ]

    return jsonify({
        "ok": True,
        "persons_home": sorted(persons_home, key=lambda p: p.get("name", "")),
        "persons_away": sorted(persons_away, key=lambda p: p.get("name", "")),
        "total_home": len(persons_home),
        "total_tracked": len(_presence_map),
        "last_updated": time.time(),
    })


@presence_bp.route("/update", methods=["POST"])
@require_token
def presence_update():
    """Receive presence update from HACS integration.

    Request body::

        {
            "persons": [
                {
                    "person_id": "person.alice",
                    "name": "Alice",
                    "state": "home",
                    "zone": "living_room",
                    "since": 1700000000.0,
                    "source": "ha"
                }
            ]
        }

    Response::

        {"ok": true, "updated": 2}
    """
    data = request.get_json(silent=True) or {}
    persons = data.get("persons")

    if not isinstance(persons, list):
        return jsonify({
            "ok": False,
            "error": "Missing or invalid field 'persons' (expected list)",
        }), 400

    updated = 0
    now = time.time()

    for p in persons:
        if not isinstance(p, dict):
            continue

        pid = str(p.get("person_id", "")).strip()
        if not pid:
            continue

        new_state = str(p.get("state", "unknown")).strip()
        old = _presence_map.get(pid)
        old_state = old.get("state") if old else None

        # Upsert person record
        _presence_map[pid] = {
            "person_id": pid,
            "name": p.get("name") or pid,
            "state": new_state,
            "zone": p.get("zone"),
            "since": p.get("since") or now,
            "source": p.get("source") or "ha",
            "updated_at": now,
        }

        # Detect state change and record history event
        if old_state is not None and old_state != new_state:
            event_type = _classify_transition(old_state, new_state)
            _presence_history.appendleft({
                "person_id": pid,
                "person_name": p.get("name") or pid,
                "event_type": event_type,
                "from_state": old_state,
                "to_state": new_state,
                "zone": p.get("zone"),
                "timestamp": now,
            })
            _LOGGER.info(
                "Presence %s: %s  %s -> %s (zone=%s)",
                event_type, p.get("name") or pid,
                old_state, new_state, p.get("zone"),
            )

        updated += 1

    return jsonify({"ok": True, "updated": updated})


@presence_bp.route("/history", methods=["GET"])
@require_token
def presence_history():
    """Return recent presence events.

    Query params:
        limit (int): Max events to return (1-200, default 50).

    Response::

        {
            "ok": true,
            "events": [
                {
                    "person_id": "person.alice",
                    "person_name": "Alice",
                    "event_type": "arrived",
                    "from_state": "not_home",
                    "to_state": "home",
                    "zone": "living_room",
                    "timestamp": 1700000000.0
                }
            ]
        }
    """
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except (TypeError, ValueError):
        limit = 50

    return jsonify({
        "ok": True,
        "events": list(_presence_history)[:limit],
    })


# ===================================================================
# LLM Context Helper
# ===================================================================

def get_presence_context_for_llm() -> str:
    """Build presence context string for LLM system prompt.

    Returns a short German-language summary like:
        "Personen: Anwesend: Alice (Wohnzimmer), Bob (zuhause). Abwesend: Charlie."

    Returns an empty string when no persons are tracked.
    """
    if not _presence_map:
        return ""

    home = [
        p for p in _presence_map.values()
        if p.get("state") not in ("not_home", "unknown")
        and p.get("state")
    ]
    away = [
        p for p in _presence_map.values()
        if p.get("state") in ("not_home", "unknown")
    ]

    parts: list[str] = []
    if home:
        names = [
            f"{p['name']} ({p.get('zone') or 'zuhause'})"
            for p in sorted(home, key=lambda p: p.get("name", ""))
        ]
        parts.append(f"Anwesend: {', '.join(names)}")
    if away:
        names_away = [
            p["name"]
            for p in sorted(away, key=lambda p: p.get("name", ""))
        ]
        parts.append(f"Abwesend: {', '.join(names_away)}")

    return "Personen: " + ". ".join(parts) + "."


# ===================================================================
# Internal Helpers
# ===================================================================

def _classify_transition(old_state: str, new_state: str) -> str:
    """Classify a state transition into an event type.

    Returns one of: ``arrived``, ``departed``, ``zone_changed``.
    """
    old_away = old_state in ("not_home", "unknown")
    new_away = new_state in ("not_home", "unknown")

    if old_away and not new_away:
        return "arrived"
    if not old_away and new_away:
        return "departed"
    # Both states are "present" but the zone changed
    return "zone_changed"


# ===================================================================
# Programmatic Access
# ===================================================================

def get_presence_map() -> dict[str, dict[str, Any]]:
    """Return a shallow copy of the current presence map.

    Useful for other modules (e.g. ProactiveEngine) that need to inspect
    who is currently tracked without going through the HTTP layer.
    """
    return dict(_presence_map)


def clear_presence_data() -> None:
    """Clear all presence data (for testing or reset)."""
    _presence_map.clear()
    _presence_history.clear()
    _LOGGER.info("Presence data cleared")
