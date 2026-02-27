"""Entity Search API v2 — Searchable entity data for Frontend + HA Integration.

Endpoints:
  GET  /api/v1/entities/search?q=<query>&domain=<domain>&area=<area>&role=<role>&manufacturer=<mfr>&limit=50
  GET  /api/v1/entities/domains    — All available domains with counts
  GET  /api/v1/entities/by-area    — Entities grouped by HA area
  POST /api/v1/entities/bulk       — Bulk import from HA Discovery (entities + areas + devices)
  GET  /api/v1/entities/zone-suggestions — Zone mapping suggestions
  GET  /api/v1/entities/stats      — Cache statistics
  GET  /api/v1/entities/devices    — Device list with manufacturer grouping
  GET  /api/v1/entities/<entity_id> — Single entity details

Data sources (per HA API docs):
  - Entity states come from REST /api/states (friendly_name, state, attributes)
  - Entity registry comes from WebSocket config/entity_registry/list (area_id, device_id, labels)
  - Device registry comes from WebSocket config/device_registry/list (manufacturer, model, area_id)
  - Area registry comes from WebSocket config/area_registry/list (name, floor_id)
  - Note: area_id is NOT available via REST /api/states — only via registry APIs.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

entity_search_bp = Blueprint("entity_search", __name__, url_prefix="/api/v1/entities")

# Entity cache (populated by HA event ingestion or bulk import)
_entity_cache: dict[str, dict[str, Any]] = {}
_area_cache: dict[str, dict[str, Any]] = {}
_device_cache: dict[str, dict[str, Any]] = {}
_last_bulk_import: float = 0.0

# Room keyword mapping for zone auto-suggestions (DE + EN)
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

# Entity role inference patterns (DE + EN)
_ROLE_PATTERNS: dict[str, list[str]] = {
    "brightness": ["lux", "helligkeit", "brightness", "illumin"],
    "noise": ["lautstärke", "noise", "laerm", "dezibel", "sound_level"],
    "humidity": ["feucht", "humidity", "luftfeucht"],
    "co2": ["co2", "kohlendioxid", "carbon"],
    "temperature": ["temperatur", "temperature", "temp_"],
    "heating": ["heiz", "heating", "thermostat", "valve", "climate."],
    "camera": ["kamera", "camera", "cam_"],
    "media": ["media_player", "sonos", "tv", "speaker", "chromecast", "apple_tv"],
    "power": ["power", "leistung", "watt"],
    "energy": ["energy", "energie", "kwh", "verbrauch"],
    "door": ["tuer", "tür", "door", "kontakt"],
    "window": ["fenster", "window"],
    "motion": ["motion", "bewegung", "presence", "occupancy", "pir"],
    "light": ["light.", "licht", "lampe", "bulb", "led"],
    "cover": ["cover.", "rollo", "shutter", "jalousie", "blind"],
    "vacuum": ["vacuum", "staubsaug", "roborock"],
    "lock": ["lock.", "schloss"],
    "alarm": ["alarm", "siren"],
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
        # Merge with existing cache entry to preserve device/area info from bulk import
        existing = _entity_cache.get(eid, {})
        _entity_cache[eid] = {
            "entity_id": eid,
            "domain": eid.split(".", 1)[0] if "." in eid else "",
            "state": entity.get("state", entity.get("state_to", "unknown")),
            "friendly_name": friendly_name,
            "device_class": device_class,
            "area_id": entity.get("area_id", "") or existing.get("area_id", ""),
            "area_name": existing.get("area_name", ""),
            "icon": icon,
            "roles": _infer_roles(eid, friendly_name, device_class),
            "device": existing.get("device", {}),
            "labels": existing.get("labels", []),
            "platform": existing.get("platform", ""),
        }


def update_area_cache(areas: list[dict[str, Any]]) -> None:
    """Update area cache from HA area data."""
    for area in areas:
        area_id = area.get("area_id", "")
        if area_id:
            _area_cache[area_id] = area


def update_device_cache(devices: list[dict[str, Any]]) -> None:
    """Update device cache from HA device data."""
    for device in devices:
        device_id = device.get("device_id", device.get("id", ""))
        if device_id:
            _device_cache[device_id] = device


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


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@entity_search_bp.route("", methods=["GET"])
@require_token
def list_entities():
    """List cached entities (v2).

    This endpoint intentionally mirrors the legacy ``/api/v1/entities`` list API
    that the dashboard expects, but it is backed by the HA discovery cache.

    Query params:
      domain: Filter by domain (e.g., 'light', 'media_player')
      state:  Filter by state (e.g., 'on', 'off', 'unavailable')
      area:   Filter by area_id
      role:   Filter by inferred role
      label:  Filter by HA label
      limit:  Max results (default 2000, max 5000)
    """
    domain_filter = request.args.get("domain", "").strip().lower()
    state_filter = request.args.get("state", "").strip().lower()
    area_filter = request.args.get("area", "").strip()
    role_filter = request.args.get("role", "").strip().lower()
    label_filter = request.args.get("label", "").strip().lower()
    limit = min(int(request.args.get("limit", 2000)), 5000)

    results: list[dict[str, Any]] = []
    for entity in _entity_cache.values():
        if domain_filter and entity.get("domain") != domain_filter:
            continue
        if state_filter and str(entity.get("state", "")).lower() != state_filter:
            continue
        if area_filter and entity.get("area_id") != area_filter:
            continue
        if role_filter and role_filter not in entity.get("roles", []):
            continue
        if label_filter:
            entity_labels = [l.lower() for l in entity.get("labels", [])]
            if label_filter not in entity_labels:
                continue
        results.append(entity)
        if len(results) >= limit:
            break

    results.sort(key=lambda e: e.get("friendly_name", e.get("entity_id", "")).lower())

    return jsonify({
        "ok": True,
        "entities": results,
        "count": len(results),
        "total_cached": len(_entity_cache),
    })


@entity_search_bp.route("/search", methods=["GET"])
@require_token
def search_entities():
    """Search entities by query string with optional filters.

    Query params:
      q: Search term (matches entity_id, friendly_name, manufacturer, model)
      domain: Filter by domain (e.g., 'light', 'media_player')
      area: Filter by area_id
      role: Filter by inferred role (e.g., 'motion', 'brightness', 'media')
      manufacturer: Filter by device manufacturer
      label: Filter by HA label
      limit: Max results (default 50, max 200)
    """
    query = request.args.get("q", "").strip().lower()
    domain_filter = request.args.get("domain", "").strip().lower()
    area_filter = request.args.get("area", "").strip()
    role_filter = request.args.get("role", "").strip().lower()
    manufacturer_filter = request.args.get("manufacturer", "").strip().lower()
    label_filter = request.args.get("label", "").strip().lower()
    limit = min(int(request.args.get("limit", 50)), 200)

    results = []
    for eid, entity in _entity_cache.items():
        if domain_filter and entity.get("domain") != domain_filter:
            continue
        if area_filter and entity.get("area_id") != area_filter:
            continue
        if role_filter and role_filter not in entity.get("roles", []):
            continue
        if manufacturer_filter:
            dev = entity.get("device", {})
            if manufacturer_filter not in (dev.get("manufacturer", "") or "").lower():
                continue
        if label_filter:
            entity_labels = [l.lower() for l in entity.get("labels", [])]
            if label_filter not in entity_labels:
                continue
        if query:
            name = entity.get("friendly_name", "").lower()
            dev = entity.get("device", {})
            mfr = (dev.get("manufacturer", "") or "").lower()
            model = (dev.get("model", "") or "").lower()
            searchable = f"{eid.lower()} {name} {mfr} {model}"
            if query not in searchable:
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


@entity_search_bp.route("/<path:entity_id>", methods=["GET"])
@require_token
def get_entity(entity_id: str):
    """Get details for a single entity."""
    # Avoid matching other routes
    if entity_id in ("search", "domains", "by-area", "bulk", "zone-suggestions", "stats", "devices"):
        return jsonify({"ok": False, "error": "reserved_path"}), 400

    entity = _entity_cache.get(entity_id)
    if not entity:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({"ok": True, "entity": entity})


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


@entity_search_bp.route("/devices", methods=["GET"])
@require_token
def list_devices():
    """List all devices grouped by manufacturer."""
    manufacturer_groups: dict[str, list[dict[str, Any]]] = {}

    for device in _device_cache.values():
        mfr = device.get("manufacturer", "") or "Unknown"
        manufacturer_groups.setdefault(mfr, []).append(device)

    result = [
        {
            "manufacturer": mfr,
            "device_count": len(devices),
            "devices": devices,
        }
        for mfr, devices in sorted(manufacturer_groups.items())
    ]

    return jsonify({
        "ok": True,
        "manufacturers": result,
        "total_devices": len(_device_cache),
        "total_manufacturers": len(result),
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
            "floor_id": area_info.get("floor_id", ""),
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
    """Bulk import entities + areas + devices from HA Discovery v2.

    Body (JSON):
      entities: list of {entity_id, domain, state, friendly_name, device_class,
                         area_id, icon, platform, labels, device: {...}, ...}
      areas: list of {area_id, name, floor_id, labels, icon, aliases}
      devices: list of {device_id, name, manufacturer, model, sw_version, area_id, labels}
    """
    global _last_bulk_import

    data = request.get_json(silent=True) or {}
    entities = data.get("entities", [])
    areas = data.get("areas", [])
    devices = data.get("devices", [])

    # Process devices first (for entity→device lookups)
    for device in devices:
        device_id = device.get("device_id", device.get("id", ""))
        if device_id:
            _device_cache[device_id] = {
                "device_id": device_id,
                "name": device.get("name", ""),
                "manufacturer": device.get("manufacturer", ""),
                "model": device.get("model", ""),
                "sw_version": device.get("sw_version", ""),
                "area_id": device.get("area_id", ""),
                "labels": device.get("labels", []),
            }

    # Process areas
    for area in areas:
        area_id = area.get("area_id", area.get("id", ""))
        if area_id:
            _area_cache[area_id] = {
                "area_id": area_id,
                "name": area.get("name", area_id),
                "floor_id": area.get("floor_id", ""),
                "labels": area.get("labels", []),
                "icon": area.get("icon", ""),
                "aliases": area.get("aliases", []),
            }

    # Process entities
    imported = 0
    for entity in entities:
        eid = entity.get("entity_id", "")
        if not eid:
            continue
        domain = entity.get("domain", eid.split(".", 1)[0] if "." in eid else "")
        friendly_name = entity.get("friendly_name", eid)
        device_class = entity.get("device_class", "")
        area_id = entity.get("area_id", "")
        area_name = _area_cache.get(area_id, {}).get("name", "") if area_id else ""

        _entity_cache[eid] = {
            "entity_id": eid,
            "domain": domain,
            "state": entity.get("state", "unknown"),
            "friendly_name": friendly_name,
            "device_class": device_class,
            "area_id": area_id,
            "area_name": area_name,
            "icon": entity.get("icon", ""),
            "unit_of_measurement": entity.get("unit_of_measurement", ""),
            "platform": entity.get("platform", ""),
            "labels": entity.get("labels", []),
            "device": entity.get("device", {}),
            "roles": _infer_roles(eid, friendly_name, device_class),
        }
        imported += 1

    _last_bulk_import = time.time()

    # Build zone suggestions from imported data
    zone_suggestions = _build_zone_suggestions()

    _LOGGER.info(
        "Bulk import: %d entities, %d areas, %d devices, %d zone suggestions",
        imported, len(areas), len(devices), len(zone_suggestions),
    )

    return jsonify({
        "ok": True,
        "imported_entities": imported,
        "imported_areas": len(areas),
        "imported_devices": len(devices),
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
    """Get entity/area/device cache statistics."""
    domain_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    manufacturer_counts: dict[str, int] = {}
    assigned_to_area = 0

    for entity in _entity_cache.values():
        domain = entity.get("domain", "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if entity.get("area_id"):
            assigned_to_area += 1
        for role in entity.get("roles", []):
            role_counts[role] = role_counts.get(role, 0) + 1

    for device in _device_cache.values():
        mfr = device.get("manufacturer", "") or "Unknown"
        manufacturer_counts[mfr] = manufacturer_counts.get(mfr, 0) + 1

    return jsonify({
        "ok": True,
        "total_entities": len(_entity_cache),
        "total_areas": len(_area_cache),
        "total_devices": len(_device_cache),
        "entities_with_area": assigned_to_area,
        "entities_without_area": len(_entity_cache) - assigned_to_area,
        "domain_counts": dict(sorted(domain_counts.items(), key=lambda x: -x[1])),
        "role_counts": dict(sorted(role_counts.items(), key=lambda x: -x[1])),
        "manufacturer_counts": dict(sorted(manufacturer_counts.items(), key=lambda x: -x[1])),
        "last_bulk_import": _last_bulk_import,
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_zone_suggestions() -> list[dict[str, Any]]:
    """Build zone mapping suggestions from cached entities + areas."""
    zone_map: dict[str, dict[str, Any]] = {}

    for entity in _entity_cache.values():
        eid = entity.get("entity_id", "")
        friendly_name = entity.get("friendly_name", "")
        area_id = entity.get("area_id", "")
        area_name = entity.get("area_name", "")
        if not area_name and area_id:
            area_name = _area_cache.get(area_id, {}).get("name", area_id)

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
        "notify": "mdi:bell",
        "calendar": "mdi:calendar",
        "todo": "mdi:checkbox-marked-outline",
    }
    return icons.get(domain, "mdi:puzzle")
