"""Presence Tracking API — v3.5.0 (Presence Aggregation Pattern).

Tracks who is home and where, receives updates from HACS integration.

Multi-Source-Aggregation:
- Combines motion/occupancy/presence sensors + BLE/device_tracker
- Any-on rule: if ANY source reports "home", person is present
- Timeout-reset: activity resets the presence timeout
- Hold-switch: manual override ignores sensor states

GET  /api/v1/presence/status  — current presence map
POST /api/v1/presence/update  — receive presence update from HACS
GET  /api/v1/presence/history — recent arrivals/departures
POST /api/v1/presence/hold    — set hold (manual override)
DELETE /api/v1/presence/hold   — clear hold
GET  /api/v1/presence/sources  — get sources for a person
POST /api/v1/presence/zone/presence/<zone_id>/hold  — set zone-level hold (HA -> Core)
POST /api/v1/presence/zone/presence/<zone_id>/state — report aggregated zone presence (HA -> Core)

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
# Config
# ---------------------------------------------------------------------------
# Timeout in seconds before a person is marked away after last update
DEFAULT_PRESENCE_TIMEOUT = 300  # 5 minutes

# Source types that contribute to presence
VALID_SOURCES = {"ha", "motion", "occupancy", "presence", "ble", "device_tracker"}

# States that count as "home"/"present"
HOME_STATES = {"home", "on", "present", "detected", "connected", "true", "1"}

# States that count as "away"/"not home"
AWAY_STATES = {"not_home", "unknown", "off", "away", "not_present", "disconnected", "false", "0", ""}


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
# Keyed by person_id -> dict with current state.
_presence_map: dict[str, dict[str, Any]] = {}

# Ring buffer of recent state-change events (newest first).
_presence_history: deque[dict[str, Any]] = deque(maxlen=200)

# Zone-level presence hold: keyed by zone_id -> hold state
# hold state: "auto" (normal), "force_on" (always occupied), "force_off" (always empty)
_ZONE_HOLD_MAP: dict[str, str] = {}


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
            "last_updated": 1700000000.0,
            "hold_active": {"person.alice": "away"}
        }
    """
    persons_home = []
    persons_away = []
    hold_active = {}

    for p in _presence_map.values():
        state = p.get("state")
        hold = p.get("hold")

        # If hold is active, use hold state, otherwise use computed state
        if hold:
            final_state = hold
            hold_active[p["person_id"]] = hold
        else:
            final_state = state

        if final_state not in AWAY_STATES and final_state:
            persons_home.append(p)
        else:
            persons_away.append(p)

    return jsonify({
        "ok": True,
        "persons_home": sorted(persons_home, key=lambda p: p.get("name", "")),
        "persons_away": sorted(persons_away, key=lambda p: p.get("name", "")),
        "total_home": len(persons_home),
        "total_tracked": len(_presence_map),
        "last_updated": time.time(),
        "hold_active": hold_active,
    })


@presence_bp.route("/update", methods=["POST"])
@require_token
def presence_update():
    """Receive presence update from HACS integration or sensors.

    Multi-source support - each source is tracked individually.

    Request body::

        {
            "persons": [
                {
                    "person_id": "person.alice",
                    "name": "Alice",
                    "state": "home",           # "home", "not_home", "unknown"
                    "zone": "living_room",
                    "source": "ha",            # "motion", "occupancy", "presence", "ble", "device_tracker"
                    "since": 1700000000.0,
                    "timeout": 300             # optional override
                }
            ]
        }

    Response::

        {"ok": true, "updated": 2, "state_changed": true}
    """
    data = request.get_json(silent=True) or {}
    persons = data.get("persons")

    if not isinstance(persons, list):
        return jsonify({
            "ok": False,
            "error": "Missing or invalid field 'persons' (expected list)",
        }), 400

    updated = 0
    state_changed = False
    now = time.time()

    for p in persons:
        if not isinstance(p, dict):
            continue

        pid = str(p.get("person_id", "")).strip()
        if not pid:
            continue

        # Validate and normalize source
        source = str(p.get("source", "ha")).strip().lower()
        if source not in VALID_SOURCES:
            source = "ha"  # Default fallback

        # Normalize state
        new_state = _normalize_state(str(p.get("state", "unknown")).strip())

        # Get person record (create if not exists)
        person = _presence_map.get(pid)
        if not person:
            person = {
                "person_id": pid,
                "name": p.get("name") or pid,
                "state": "unknown",
                "sources": {},
                "hold": None,
                "hold_reason": None,
                "since": now,
                "updated_at": now,
            }
            _presence_map[pid] = person

        # Get old aggregated state (ignoring hold for comparison)
        old_state = person.get("state")
        old_sources = person.get("sources", {})

        # Update source-specific state
        old_source_state = old_sources.get(source)
        old_sources[source] = {
            "state": new_state,
            "zone": p.get("zone"),
            "since": p.get("since") or now,
            "updated_at": now,
            "timeout": p.get("timeout") or DEFAULT_PRESENCE_TIMEOUT,
        }
        person["sources"] = old_sources

        # Compute new aggregated state using any-on rule
        # If ANY source reports home, person is home
        aggregated_state = _aggregate_sources(old_sources, person.get("hold"))

        # Apply hold override
        if person.get("hold"):
            aggregated_state = person["hold"]

        # Update main state
        old_actual_state = person.get("state")
        person["state"] = aggregated_state
        person["name"] = p.get("name") or person.get("name") or pid
        person["zone"] = p.get("zone") or person.get("zone")
        person["updated_at"] = now

        # If no "since" yet, set it
        if person.get("since") is None or (aggregated_state in HOME_STATES and old_actual_state in AWAY_STATES):
            person["since"] = now

        # Detect and log state change
        if old_actual_state != aggregated_state:
            state_changed = True
            event_type = _classify_transition(old_actual_state, aggregated_state)
            _presence_history.appendleft({
                "person_id": pid,
                "person_name": person.get("name"),
                "event_type": event_type,
                "from_state": old_actual_state,
                "to_state": aggregated_state,
                "trigger_source": source,
                "zone": p.get("zone"),
                "timestamp": now,
            })
            _LOGGER.info(
                "Presence %s: %s  %s -> %s (source=%s, zone=%s)",
                event_type, person.get("name"),
                old_actual_state, aggregated_state, source, p.get("zone"),
            )

        updated += 1

    return jsonify({"ok": True, "updated": updated, "state_changed": state_changed})


@presence_bp.route("/hold", methods=["POST"])
@require_token
def presence_hold():
    """Set hold (manual override) for a person.

    When hold is active, the person's state is fixed regardless of sensor updates.

    Request body::

        {
            "person_id": "person.alice",
            "state": "home",      # "home" or "away"
            "reason": "manual",   # optional reason
            "duration": 3600      # optional: auto-clear after seconds
        }

    Response::

        {"ok": true, "hold_set": "home", "person_id": "person.alice"}
    """
    data = request.get_json(silent=True) or {}
    pid = str(data.get("person_id", "")).strip()

    if not pid:
        return jsonify({"ok": False, "error": "Missing person_id"}), 400

    hold_state = _normalize_state(str(data.get("state", "home")).strip())
    if hold_state not in HOME_STATES and hold_state not in AWAY_STATES:
        hold_state = "home"

    reason = data.get("reason", "manual")
    duration = data.get("duration")  # Optional auto-expire

    person = _presence_map.get(pid)
    if not person:
        # Create new person record with hold
        person = {
            "person_id": pid,
            "name": pid,
            "state": hold_state,
            "sources": {},
            "hold": hold_state,
            "hold_reason": reason,
            "hold_until": time.time() + duration if duration else None,
            "since": time.time(),
            "updated_at": time.time(),
        }
        _presence_map[pid] = person
    else:
        # Update existing with hold
        old_state = person.get("state")
        person["hold"] = hold_state
        person["hold_reason"] = reason
        person["hold_until"] = time.time() + duration if duration else None
        person["state"] = hold_state
        person["updated_at"] = time.time()

        # Log state change due to hold
        if old_state != hold_state:
            _presence_history.appendleft({
                "person_id": pid,
                "person_name": person.get("name"),
                "event_type": _classify_transition(old_state, hold_state),
                "from_state": old_state,
                "to_state": hold_state,
                "trigger_source": "hold",
                "reason": reason,
                "timestamp": time.time(),
            })
            _LOGGER.info("Presence hold: %s -> %s (reason: %s)", person.get("name"), hold_state, reason)

    return jsonify({
        "ok": True,
        "hold_set": hold_state,
        "person_id": pid,
        "reason": reason,
        "hold_until": person.get("hold_until"),
    })


@presence_bp.route("/hold", methods=["DELETE"])
@require_token
def presence_hold_clear():
    """Clear hold (manual override) for a person.

    Query params:
        person_id (str): Required person ID

    Response::

        {"ok": true, "hold_cleared": "person.alice", "current_state": "home"}
    """
    pid = request.args.get("person_id", "").strip()

    if not pid:
        return jsonify({"ok": False, "error": "Missing person_id"}), 400

    person = _presence_map.get(pid)
    if not person:
        return jsonify({"ok": False, "error": "Person not found"}), 404

    # Clear hold and recompute state
    old_hold = person.get("hold")
    person.pop("hold", None)
    person.pop("hold_reason", None)
    person.pop("hold_until", None)

    # Recompute from sources
    aggregated_state = _aggregate_sources(person.get("sources", {}), None)
    old_state = person.get("state")
    person["state"] = aggregated_state
    person["updated_at"] = time.time()

    # Log change
    if old_state != aggregated_state:
        _presence_history.appendleft({
            "person_id": pid,
            "person_name": person.get("name"),
            "event_type": _classify_transition(old_state, aggregated_state),
            "from_state": old_state,
            "to_state": aggregated_state,
            "trigger_source": "hold_cleared",
            "timestamp": time.time(),
        })

    _LOGGER.info("Presence hold cleared: %s, state now: %s", pid, aggregated_state)

    return jsonify({
        "ok": True,
        "hold_cleared": pid,
        "current_state": aggregated_state,
    })


# =============================================================================
# Zone-level presence hold (HA -> Core, for AreaPresenceSensor)
# =============================================================================

@presence_bp.route("/presence/zone/presence/<zone_id>/hold", methods=["POST"])
@presence_bp.route("/zone/presence/<zone_id>/hold", methods=["POST"])
@require_token
def zone_presence_hold(zone_id: str):
    """Set zone-level presence hold state from HA AreaPresenceSensor.

    HA calls this when user toggles hold switch in dashboard:
    - auto: normal any-on aggregation
    - force_on: zone always occupied
    - force_off: zone always empty

    Body::

        {"hold": "auto" | "force_on" | "force_off"}

    Response::

        {"ok": true, "zone_id": "zone:living", "hold": "force_on"}
    """
    VALID_HOLD_STATES = {"auto", "force_on", "force_off"}
    data = request.get_json(silent=True) or {}
    hold = str(data.get("hold", "auto")).strip()

    if hold not in VALID_HOLD_STATES:
        return jsonify({
            "ok": False,
            "error": f"Invalid hold state: {hold}. Must be one of: {VALID_HOLD_STATES}"
        }), 400

    # Store zone-level hold in a separate dict (not per-person)
    if not hasattr(presence_bp, "_zone_hold_map"):
        presence_bp._zone_hold_map = {}

    old_hold = presence_bp._zone_hold_map.get(zone_id, "auto")
    presence_bp._zone_hold_map[zone_id] = hold

    _LOGGER.info(
        "Zone presence hold: %s %s -> %s",
        zone_id, old_hold, hold
    )

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "hold": hold,
    })


@presence_bp.route("/presence/zone/presence/<zone_id>/state", methods=["POST"])
@presence_bp.route("/zone/presence/<zone_id>/state", methods=["POST"])
@require_token
def zone_presence_state(zone_id: str):
    """Receive aggregated presence state from HA AreaPresenceSensor.

    HA's any-on aggregation (all persons in zone) is authoritative when
    Core is unreachable. Called at most once per 30 s per zone (throttled by HA).

    Body::

        {
            "occupied": true | false,
            "primary_source": "person.alice",
            "confidence": 0.95,
            "hold_state": "auto" | "force_on" | "force_off"
        }

    Response::

        {"ok": true, "zone_id": "zone:living", "stored": true}
    """
    data = request.get_json(silent=True) or {}
    occupied = bool(data.get("occupied", False))
    primary_source = data.get("primary_source")
    confidence = float(data.get("confidence", 0.0))
    hold_state = str(data.get("hold_state", "auto")).strip()

    # Validate zone_id format
    if not zone_id.startswith("zone:"):
        zone_id = f"zone:{zone_id}"

    # Store in zone presence state map (used by Brain/Neurons)
    if not hasattr(presence_bp, "_zone_presence_state"):
        presence_bp._zone_presence_state = {}

    now = time.time()
    presence_bp._zone_presence_state[zone_id] = {
        "occupied": occupied,
        "primary_source": primary_source,
        "confidence": confidence,
        "hold_state": hold_state,
        "updated_at": now,
    }

    _LOGGER.debug(
        "Zone presence state: %s occupied=%s source=%s",
        zone_id, occupied, primary_source
    )

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "occupied": occupied,
        "stored": True,
    })


def get_zone_presence_state(zone_id: str) -> dict[str, Any] | None:
    """Return stored zone presence state (for Neurons/Brain access)."""
    if not hasattr(presence_bp, "_zone_presence_state"):
        return None
    return presence_bp._zone_presence_state.get(zone_id)


def get_zone_hold_state(zone_id: str) -> str:
    """Return zone-level hold state (defaults to 'auto')."""
    if not hasattr(presence_bp, "_zone_hold_map"):
        return "auto"
    return presence_bp._zone_hold_map.get(zone_id, "auto")


# =============================================================================
# Sources
# =============================================================================

@presence_bp.route("/sources", methods=["GET"])
@require_token
def presence_sources():
    """Get all sources for a person.

    Query params:
        person_id (str): Required person ID

    Response::

        {
            "ok": true,
            "person_id": "person.alice",
            "sources": {
                "ha": {"state": "home", "zone": "living_room", "updated_at": 1700000000.0},
                "ble": {"state": "home", "zone": "entry", "updated_at": 1700000000.0},
                "motion": {"state": "not_home", ...}
            },
            "hold": "home",
            "aggregated_state": "home"
        }
    """
    pid = request.args.get("person_id", "").strip()

    if not pid:
        return jsonify({"ok": False, "error": "Missing person_id"}), 400

    person = _presence_map.get(pid)
    if not person:
        return jsonify({"ok": False, "error": "Person not found"}), 404

    return jsonify({
        "ok": True,
        "person_id": pid,
        "name": person.get("name"),
        "sources": person.get("sources", {}),
        "hold": person.get("hold"),
        "hold_reason": person.get("hold_reason"),
        "aggregated_state": person.get("state"),
    })


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
                    "trigger_source": "ble",
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


@presence_bp.route("/check_timeouts", methods=["POST"])
@require_token
def presence_check_timeouts():
    """Check for timed-out sources and update presence accordingly.

    This endpoint should be called periodically (e.g., every minute) to
    handle timeout-reset logic.

    Response::

        {"ok": true, "timed_out": [], "state_changed": false}
    """
    now = time.time()
    timed_out = []
    state_changed = False

    for pid, person in list(_presence_map.items()):
        sources = person.get("sources", {})
        hold = person.get("hold")

        # Check hold expiration
        hold_until = person.get("hold_until")
        if hold_until and now >= hold_until:
            _LOGGER.info("Hold expired for %s", pid)
            person.pop("hold", None)
            person.pop("hold_reason", None)
            person.pop("hold_until", None)
            # Will recompute below

        # Check each source for timeout
        had_activity = False
        for source, source_data in list(sources.items()):
            timeout = source_data.get("timeout", DEFAULT_PRESENCE_TIMEOUT)
            updated_at = source_data.get("updated_at", 0)
            elapsed = now - updated_at

            if elapsed > timeout:
                # Source timed out - set to away
                if source_data.get("state") not in AWAY_STATES:
                    _LOGGER.debug("Source %s for %s timed out after %ds", source, pid, elapsed)
                    source_data["state"] = "not_home"
                    had_activity = True

        # Recompute aggregated state if not on hold
        if not person.get("hold"):
            old_state = person.get("state")
            aggregated_state = _aggregate_sources(sources, None)
            person["state"] = aggregated_state

            if old_state != aggregated_state:
                state_changed = True
                timed_out.append(pid)
                event_type = _classify_transition(old_state, aggregated_state)
                _presence_history.appendleft({
                    "person_id": pid,
                    "person_name": person.get("name"),
                    "event_type": event_type,
                    "from_state": old_state,
                    "to_state": aggregated_state,
                    "trigger_source": "timeout",
                    "timestamp": now,
                })
                _LOGGER.info("Presence timeout: %s %s -> %s", person.get("name"), old_state, aggregated_state)

    return jsonify({
        "ok": True,
        "timed_out": timed_out,
        "state_changed": state_changed,
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

    home = []
    away = []

    for p in _presence_map.values():
        state = p.get("state")
        hold = p.get("hold")

        # If hold is active, use hold state
        if hold:
            final_state = hold
        else:
            final_state = state

        if final_state not in AWAY_STATES and final_state:
            home.append(p)
        else:
            away.append(p)

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

def _normalize_state(state: str) -> str:
    """Normalize state string to canonical form.

    Returns "home", "not_home", or "unknown".
    """
    state_lower = state.lower().strip()

    if state_lower in HOME_STATES:
        return "home"
    elif state_lower in AWAY_STATES:
        return "not_home"
    else:
        return "unknown"


def _aggregate_sources(sources: dict[str, Any], hold: str | None = None) -> str:
    """Aggregate multiple sources using any-on rule.

    If ANY source reports "home", the person is considered home.
    Only if ALL sources are "not_home" or "unknown", the person is away.

    This is the core Multi-Source-Aggregation logic.

    Args:
        sources: Dict of source_name -> source_data
        hold: Optional hold state override

    Returns:
        "home", "not_home", or "unknown"
    """
    # If hold is active, use hold state
    if hold:
        return hold

    if not sources:
        return "unknown"

    # Any-on rule: if ANY source is home, person is home
    for source_name, source_data in sources.items():
        source_state = source_data.get("state", "unknown")
        if source_state in HOME_STATES:
            return "home"

    # Check if any source reports unknown
    for source_name, source_data in sources.items():
        source_state = source_data.get("state", "unknown")
        if source_state == "unknown":
            return "unknown"

    # All sources are away/not_home
    return "not_home"


def _classify_transition(old_state: str, new_state: str) -> str:
    """Classify a state transition into an event type.

    Returns one of: ``arrived``, ``departed``, ``zone_changed``.
    """
    old_away = old_state in ("not_home", "unknown") or old_state in AWAY_STATES
    new_away = new_state in ("not_home", "unknown") or new_state in AWAY_STATES

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


def get_person_state(person_id: str) -> str | None:
    """Get current state for a specific person."""
    person = _presence_map.get(person_id)
    if person:
        return person.get("state")
    return None


def set_person_state(person_id: str, state: str, source: str = "api", zone: str | None = None) -> bool:
    """Programmatically set presence state for a person.

    This is the timeout-reset mechanism - calling this updates the source
    and resets the timeout timer.

    Args:
        person_id: The person identifier
        state: "home", "not_home", or "unknown"
        source: The source of the update (e.g., "motion", "ble")
        zone: Optional zone

    Returns:
        True if state changed, False otherwise
    """
    now = time.time()

    person = _presence_map.get(person_id)
    if not person:
        person = {
            "person_id": person_id,
            "name": person_id,
            "state": "unknown",
            "sources": {},
            "hold": None,
            "since": now,
            "updated_at": now,
        }
        _presence_map[person_id] = person

    old_state = person.get("state")
    sources = person.get("sources", {})

    # Update source
    sources[source] = {
        "state": state,
        "zone": zone,
        "since": now,
        "updated_at": now,
        "timeout": DEFAULT_PRESENCE_TIMEOUT,
    }
    person["sources"] = sources

    # Aggregate (respect hold)
    new_state = _aggregate_sources(sources, person.get("hold"))

    # Update person
    person["state"] = new_state
    person["updated_at"] = now

    if zone:
        person["zone"] = zone

    return new_state != old_state


def clear_presence_data() -> None:
    """Clear all presence data (for testing or reset)."""
    _presence_map.clear()
    _presence_history.clear()
    _LOGGER.info("Presence data cleared")