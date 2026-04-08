"""Entity Assignment Suggestions API — v3.2.2.

Analyzes HA entity IDs and groups them by inferred room/area,
giving the user smart suggestions for Habitus zone assignment.

GET /api/v1/entity-assignment/suggestions
  Returns: {ok, suggestions: [{room_hint, entities, confidence, entity_count}]}
"""
from __future__ import annotations

import logging
import os
import re
from collections import defaultdict

import requests
from flask import Blueprint, jsonify

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

entity_assignment_bp = Blueprint("entity_assignment", __name__, url_prefix="/api/v1/entity-assignment")

SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")

# Domains worth suggesting for zone assignment
RELEVANT_DOMAINS = {
    "light", "binary_sensor", "sensor", "climate",
    "switch", "cover", "fan", "lock", "media_player",
}

# Words that don't indicate a room (strip from entity_id)
NOISE_WORDS = {
    "sensor", "binary", "motion", "presence", "occupancy",
    "temperature", "humidity", "co2", "lux", "brightness",
    "decke", "wand", "boden", "tisch", "haupt", "haupt",
    "light", "switch", "climate", "cover", "fan", "lock",
    "1", "2", "3", "4", "a", "b", "c",
    "entry", "main", "secondary", "primary", "aux",
}

# Confidence boost per domain combination found in a room group
_DOMAIN_BONUS = {
    frozenset({"light", "binary_sensor"}): 0.2,
    frozenset({"light", "sensor"}): 0.15,
    frozenset({"light", "climate"}): 0.25,
}


def _room_hint_from_entity_id(entity_id: str) -> str | None:
    """Extract a room hint from entity_id by stripping domain and noise words.

    light.wohnzimmer_decke_1 → "wohnzimmer"
    binary_sensor.motion_bad → "bad"
    sensor.temperature_kueche_1 → "kueche"
    """
    # Remove domain prefix
    if "." not in entity_id:
        return None
    _, name = entity_id.split(".", 1)

    # Split on underscore and remove noise
    parts = name.split("_")
    meaningful = [p for p in parts if p.lower() not in NOISE_WORDS and len(p) > 2]

    if not meaningful:
        return None

    # First meaningful part is usually the room
    return meaningful[0].lower()


def _fetch_states() -> list[dict]:
    """Call HA Supervisor API to get all entity states."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        return []
    try:
        resp = requests.get(
            f"{SUPERVISOR_API}/states",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            return data if isinstance(data, list) else []
    except Exception as exc:
        _LOGGER.warning("Failed to fetch HA states: %s", exc)
    return None


@entity_assignment_bp.route("/suggestions", methods=["GET"])
@require_token
def get_suggestions():
    """Return entity groupings with zone assignment suggestions."""
    states = _fetch_states()
    if states is None:
        return jsonify({"ok": False, "error": "Supervisor API nicht erreichbar", "suggestions": []})
    if not states:
        return jsonify({"ok": True, "suggestion_count": 0, "suggestions": []})

    # Group entities by room hint
    groups: dict[str, list[dict]] = defaultdict(list)
    for state in states:
        eid = state.get("entity_id", "")
        domain = eid.split(".")[0] if "." in eid else ""
        if domain not in RELEVANT_DOMAINS:
            continue
        hint = _room_hint_from_entity_id(eid)
        if not hint:
            continue
        groups[hint].append({
            "entity_id": eid,
            "domain": domain,
            "state": state.get("state", "unknown"),
            "friendly_name": (state.get("attributes") or {}).get("friendly_name", eid),
        })

    # Build suggestions sorted by confidence descending
    suggestions = []
    for room_hint, entities in groups.items():
        if len(entities) < 2:
            # Single-entity groups are not very useful
            continue

        domains_present = {e["domain"] for e in entities}
        base_confidence = min(0.3 + len(entities) * 0.07, 0.85)

        # Bonus for having motion + light, or light + climate
        for combo, bonus in _DOMAIN_BONUS.items():
            if combo.issubset(domains_present):
                base_confidence = min(base_confidence + bonus, 0.95)
                break

        suggested_zone_id = f"zone:{room_hint}"
        suggestions.append({
            "room_hint": room_hint,
            "suggested_zone_id": suggested_zone_id,
            "entity_count": len(entities),
            "confidence": round(base_confidence, 2),
            "domains": sorted(domains_present),
            "entities": sorted(entities, key=lambda e: e["entity_id"]),
        })

    suggestions.sort(key=lambda s: (-s["confidence"], -s["entity_count"]))

    return jsonify({
        "ok": True,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions[:30],  # cap at 30
    })
