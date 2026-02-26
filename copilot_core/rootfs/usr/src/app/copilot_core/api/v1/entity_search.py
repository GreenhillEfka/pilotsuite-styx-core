"""Entity Search API - Suchbare Entity-Dropdown-Daten fuer Frontend.

Endpunkte:
  GET  /api/v1/entities/search?q=<query>&domain=<domain>&area=<area>&limit=50
  GET  /api/v1/entities/domains    — Alle verfuegbaren Domains mit Counts
  GET  /api/v1/entities/by-area    — Entities gruppiert nach HA-Area
  POST /api/v1/entities/bulk       — Bulk-Import von HA-Discovery-Daten
  GET  /api/v1/entities/zone-suggestions — Zone-Mapping-Vorschlaege
  GET  /api/v1/entities/stats      — Cache-Statistiken

Diese API liefert die Daten fuer suchbare Entity-Dropdowns
im React-Backend und in der HA-Integration.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

entity_search_bp = Blueprint("entity_search", __name__, url_prefix="/api/v1/entities")

# Entity cache (populated by HA event ingestion or bulk import)
_entity_cache: dict[str, dict[str, Any]] = {}
_area_cache: dict[str, dict[str, Any]] = {}
_last_bulk_import: float = 0.0

# Room keyword mapping for zone auto-suggestions
_ZONE_KEYWORDS: dict[str, list[str]] = {
    "wohnzimmer": ["wohnzimmer", "wohn", "living", "lounge"],
    "schlafzimmer": ["schlafzimmer", "schlaf", "bedroom", "bed"],
    "kueche": ["kueche", "küche", "kitchen"],
    "bad": ["bad", "badezimmer", "bath", "bathroom"],
    "buero": ["buero", "büro", "office", "arbeit"],
    "kinderzimmer": ["kinder", "child", "kids", "nursery"],
    "flur": ["flur", "corridor", "hallway", "eingang", "diele"],
    "garten": ["garten", "garden", "terrasse", "balkon", "outdoor", "aussen"],
    "garage": ["garage", "carport"],
    "keller": ["keller", "basement"],
    "gaeste": ["gäste", "gaeste", "guest"],
    "esszimmer": ["esszimmer", "essen", "dining"],
    "waschkueche": ["waschkueche", "waschküche", "laundry", "utility"],
    "dachboden": ["dachboden", "attic", "dach"],
}

# Entity role inference patterns
_ROLE_PATTERNS: dict[str, list[str]] = {
    "brightness": ["lux", "helligkeit", "brightness", "illumin"],
    "noise": ["lautstärke", "noise", "laerm", "dezibel", "sound_level"],
    "humidity": ["feucht", "humidity", "luftfeucht"],
    "co2": ["co2", "kohlendioxid", "carbon"],
    "temperature": ["temperatur", "temperature", "temp_"],
    "heating": ["heiz", "heating", "thermostat", "valve"],
    "camera": ["kamera", "camera", "cam_"],
    "media": ["media_player", "sonos", "tv", "speaker", "chromecast", "apple_tv"],
    "power": ["power", "leistung", "watt"],
    "energy": ["energy", "energie", "kwh", "verbrauch"],
    "door": ["tuer", "door", "kontakt"],
    "window": ["fenster", "window"],
    "motion": ["motion", "bewegung", "presence", "occupancy", "pir"],
    "light": ["light.", "licht", "lampe", "bulb", "led"],
}


def update_entity_cache(entities: list[dict[str, Any]]) -> None:
    """Update entity cache from HA state data (called by event ingest)."""
    for entity in entities:
        eid = entity.get("entity_id", "")
        if not eid:
            continue
        attrs = entity.get("attributes", {})
        if isinstance(attrs, dict):
            friendly_name = attrs.get("friendly_name", eid)
            device_class = attrs.get("device_class", "")
            icon = attrs.get("icon", "")
        else:
            friendly_name = eid
            device_class = ""
            icon = ""
        _entity_cache[eid] = {
            "entity_id": eid,
            "domain": eid.split(".", 1)[0] if "." in eid else "",
            "state": entity.get("state", entity.get("state_to", "unknown")),
            "friendly_name": friendly_name,
            "device_class": device_class,
            "area_id": entity.get("area_id", ""),
            "icon": icon,
            "roles": _infer_roles(eid, friendly_name, device_class),
        }


def update_area_cache(areas: list[dict[str, Any]]) -> None:
    """Update area cache from HA area data."""
    for area in areas:
        area_id = area.get("area_id", "")
        if area_id:
            _area_cache[area_id] = area


def _infer_roles(entity_id: str, friendly_name: str, device_class: str) -> list[str]:
    """Infer Habitus roles from entity metadata."""
    roles = []
    combined = f"{entity_id} {friendly_name} {device_class}".lower()
    for role, patterns in _ROLE_PATTERNS.items():
        if any(p in combined for p in patterns):
            roles.append(role)
    return roles


def _suggest_zone(entity_id: str, friendly_name: str, area_name: str) -> str:
    """Suggest a zone based on entity/area name."""
    combined = f"{entity_id} {friendly_name} {area_name}".lower()
    for zone_id, keywords in _ZONE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return f"zone:{zone_id}"
    return ""


@entity_search_bp.route("/search", methods=["GET"])
@require_token
def search_entities():
    """Search entities by query string with optional domain/area/role filter.

    Query params:
      q: Search term (matches entity_id and friendly_name)
      domain: Filter by domain (e.g., 'light', 'media_player')
      area: Filter by area_id
      role: Filter by inferred role (e.g., 'motion', 'brightness', 'media')
      limit: Max results (default 50, max 200)
    """
    query = request.args.get("q", "").strip().lower()
    domain_filter = request.args.get("domain", "").strip().lower()
    area_filter = request.args.get("area", "").strip()
    role_filter = request.args.get("role", "").strip().lower()
    limit = min(int(request.args.get("limit", 50)), 200)

    results = []
    for eid, entity in _entity_cache.items():
        if domain_filter and entity.get("domain") != domain_filter:
            continue
        if area_filter and entity.get("area_id") != area_filter:
            continue
        if role_filter and role_filter not in entity.get("roles", []):
            continue
        if query:
            name = entity.get("friendly_name", "").lower()
            if query not in eid.lower() and query not in name:
                continue
        results.append(entity)
        if len(results) >= limit:
            break

    results.sort(key=lambda e: (
        0 if query and e["entity_id"].lower().startswith(query) else 1,
        e.get("friendly_name", e["entity_id"]).lower(),
    ))

    return jsonify({
        "ok": True,
        "entities": results,
        "count": len(results),
        "total_cached": len(_entity_cache),
    })


@entity_search_bp.route("/domains", methods=["GET"])
@require_token
def list_domains():
    """List all entity domains with counts and icons."""
    domain_counts: dict[str, int] = {}
    for entity in _entity_cache.values():
        domain = entity.get("domain", "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    domains = [
        {"domain": d, "count": c, "icon": _domain_icon(d)}
        for d, c in sorted(domain_counts.items(), key=lambda x: -x[1])
    ]

    return jsonify({
        "ok": True,
        "domains": domains,
        "total_domains": len(domains),
        "total_entities": len(_entity_cache),
    })


@entity_search_bp.route("/by-area", methods=["GET"])
@require_token
def entities_by_area():
    """Get entities grouped by HA area with role inference."""
    area_groups: dict[str, list[dict[str, Any]]] = {"_unassigned": []}

    for entity in _entity_cache.values():
        area_id = entity.get("area_id", "")
        if area_id:
            area_groups.setdefault(area_id, []).append(entity)
        else:
            area_groups["_unassigned"].append(entity)

    result = []
    for area_id, entities in sorted(area_groups.items()):
        area_info = _area_cache.get(area_id, {})
        zone_suggestion = ""
        area_name = area_info.get("name", area_id)
        for kw_zone, keywords in _ZONE_KEYWORDS.items():
            if any(kw in area_name.lower() for kw in keywords):
                zone_suggestion = f"zone:{kw_zone}"
                break

        # Aggregate roles across entities in this area
        all_roles: set[str] = set()
        for e in entities:
            all_roles.update(e.get("roles", []))

        result.append({
            "area_id": area_id,
            "area_name": area_name,
            "entities": entities,
            "entity_count": len(entities),
            "zone_suggestion": zone_suggestion,
            "available_roles": sorted(all_roles),
        })

    return jsonify({
        "ok": True,
        "areas": result,
        "area_count": len(result),
    })


@entity_search_bp.route("/bulk", methods=["POST"])
@require_token
def bulk_import():
    """Bulk import entities + areas from HA discovery.

    Body (JSON):
      entities: list of {entity_id, domain, state, friendly_name, device_class, area_id, icon, ...}
      areas: list of {area_id, name}
      zone_mapping_suggestions: optional list of {zone_id, zone_name, entity_ids}
    """
    global _last_bulk_import

    data = request.get_json(silent=True) or {}
    entities = data.get("entities", [])
    areas = data.get("areas", [])

    # Process entities
    imported = 0
    for entity in entities:
        eid = entity.get("entity_id", "")
        if not eid:
            continue
        domain = entity.get("domain", eid.split(".", 1)[0] if "." in eid else "")
        friendly_name = entity.get("friendly_name", eid)
        device_class = entity.get("device_class", "")
        _entity_cache[eid] = {
            "entity_id": eid,
            "domain": domain,
            "state": entity.get("state", "unknown"),
            "friendly_name": friendly_name,
            "device_class": device_class,
            "area_id": entity.get("area_id", ""),
            "icon": entity.get("icon", ""),
            "unit_of_measurement": entity.get("unit_of_measurement", ""),
            "roles": _infer_roles(eid, friendly_name, device_class),
        }
        imported += 1

    # Process areas
    for area in areas:
        area_id = area.get("area_id", area.get("id", ""))
        if area_id:
            _area_cache[area_id] = {
                "area_id": area_id,
                "name": area.get("name", area_id),
            }

    _last_bulk_import = time.time()

    # Build zone suggestions from imported data
    zone_suggestions = _build_zone_suggestions()

    _LOGGER.info(
        "Bulk import: %d entities, %d areas, %d zone suggestions",
        imported, len(areas), len(zone_suggestions),
    )

    return jsonify({
        "ok": True,
        "imported_entities": imported,
        "imported_areas": len(areas),
        "zone_suggestions": zone_suggestions,
    })


@entity_search_bp.route("/zone-suggestions", methods=["GET"])
@require_token
def zone_suggestions():
    """Get zone mapping suggestions based on cached entities + areas."""
    suggestions = _build_zone_suggestions()
    return jsonify({
        "ok": True,
        "suggestions": suggestions,
        "total_entities": len(_entity_cache),
    })


@entity_search_bp.route("/stats", methods=["GET"])
@require_token
def cache_stats():
    """Get entity/area cache statistics."""
    domain_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    assigned_to_area = 0

    for entity in _entity_cache.values():
        domain = entity.get("domain", "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if entity.get("area_id"):
            assigned_to_area += 1
        for role in entity.get("roles", []):
            role_counts[role] = role_counts.get(role, 0) + 1

    return jsonify({
        "ok": True,
        "total_entities": len(_entity_cache),
        "total_areas": len(_area_cache),
        "entities_with_area": assigned_to_area,
        "entities_without_area": len(_entity_cache) - assigned_to_area,
        "domain_counts": dict(sorted(domain_counts.items(), key=lambda x: -x[1])),
        "role_counts": dict(sorted(role_counts.items(), key=lambda x: -x[1])),
        "last_bulk_import": _last_bulk_import,
    })


def _build_zone_suggestions() -> list[dict[str, Any]]:
    """Build zone mapping suggestions from cached entities + areas."""
    zone_map: dict[str, dict[str, Any]] = {}

    for entity in _entity_cache.values():
        eid = entity.get("entity_id", "")
        friendly_name = entity.get("friendly_name", "")
        area_id = entity.get("area_id", "")
        area_name = _area_cache.get(area_id, {}).get("name", area_id) if area_id else ""

        zone_id = _suggest_zone(eid, friendly_name, area_name)
        if not zone_id:
            continue

        if zone_id not in zone_map:
            zone_name = zone_id.replace("zone:", "").replace("_", " ").title()
            zone_map[zone_id] = {
                "zone_id": zone_id,
                "zone_name": zone_name,
                "entity_ids": [],
                "role_entities": {},
                "from_areas": set(),
            }
        zone_map[zone_id]["entity_ids"].append(eid)
        if area_name:
            zone_map[zone_id]["from_areas"].add(area_name)

        # Organize by role
        for role in entity.get("roles", []):
            zone_map[zone_id]["role_entities"].setdefault(role, []).append(eid)

    result = []
    for zone_id, data in sorted(zone_map.items()):
        result.append({
            "zone_id": zone_id,
            "zone_name": data["zone_name"],
            "entity_count": len(data["entity_ids"]),
            "entity_ids": data["entity_ids"],
            "role_entities": data["role_entities"],
            "from_areas": sorted(data["from_areas"]),
        })

    return result


def _domain_icon(domain: str) -> str:
    """Map domain to MDI icon."""
    icons = {
        "light": "mdi:lightbulb",
        "switch": "mdi:toggle-switch",
        "sensor": "mdi:eye",
        "binary_sensor": "mdi:checkbox-marked-circle",
        "climate": "mdi:thermostat",
        "media_player": "mdi:play-circle",
        "camera": "mdi:video",
        "cover": "mdi:window-shutter",
        "lock": "mdi:lock",
        "fan": "mdi:fan",
        "vacuum": "mdi:robot-vacuum",
        "person": "mdi:account",
        "automation": "mdi:robot",
        "scene": "mdi:palette",
        "script": "mdi:script-text",
        "input_boolean": "mdi:toggle-switch-outline",
        "input_number": "mdi:numeric",
        "input_select": "mdi:format-list-bulleted",
        "input_text": "mdi:form-textbox",
        "number": "mdi:numeric",
        "select": "mdi:format-list-bulleted",
        "button": "mdi:gesture-tap-button",
        "water_heater": "mdi:water-boiler",
        "update": "mdi:package-up",
        "weather": "mdi:weather-cloudy",
        "device_tracker": "mdi:crosshairs-gps",
        "zone": "mdi:map-marker-radius",
        "sun": "mdi:white-balance-sunny",
        "timer": "mdi:timer-outline",
        "alarm_control_panel": "mdi:shield-lock",
        "humidifier": "mdi:air-humidifier",
        "siren": "mdi:alarm-light",
        "tts": "mdi:speaker-message",
        "remote": "mdi:remote",
        "image": "mdi:image",
    }
    return icons.get(domain, "mdi:puzzle")
