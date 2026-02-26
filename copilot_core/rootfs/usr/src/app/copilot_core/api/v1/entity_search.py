"""Entity Search API - Suchbare Entity-Dropdown-Daten fuer Frontend.

Endpunkte:
  GET /api/v1/entities/search?q=<query>&domain=<domain>&limit=50
  GET /api/v1/entities/domains  Alle verfuegbaren Domains mit Counts
  GET /api/v1/entities/by-area  Entities gruppiert nach HA-Area

Diese API liefert die Daten fuer suchbare Entity-Dropdowns
im React-Backend und in der HA-Integration.
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

entity_search_bp = Blueprint("entity_search", __name__, url_prefix="/api/v1/entities")

# Entity cache (populated by HA event ingestion)
_entity_cache: dict[str, dict[str, Any]] = {}
_area_cache: dict[str, dict[str, Any]] = {}


def update_entity_cache(entities: list[dict[str, Any]]) -> None:
    """Update entity cache from HA state data (called by event ingest)."""
    for entity in entities:
        eid = entity.get("entity_id", "")
        if eid:
            _entity_cache[eid] = {
                "entity_id": eid,
                "domain": eid.split(".", 1)[0] if "." in eid else "",
                "state": entity.get("state", "unknown"),
                "friendly_name": entity.get("attributes", {}).get("friendly_name", eid),
                "device_class": entity.get("attributes", {}).get("device_class", ""),
                "area_id": entity.get("area_id", ""),
                "icon": entity.get("attributes", {}).get("icon", ""),
            }


def update_area_cache(areas: list[dict[str, Any]]) -> None:
    """Update area cache from HA area data."""
    for area in areas:
        area_id = area.get("area_id", "")
        if area_id:
            _area_cache[area_id] = area


@entity_search_bp.route("/search", methods=["GET"])
@require_token
def search_entities():
    """Search entities by query string with optional domain filter.

    Query params:
      q: Search term (matches entity_id and friendly_name)
      domain: Filter by domain (e.g., 'light', 'media_player')
      area: Filter by area_id
      limit: Max results (default 50, max 200)
    """
    query = request.args.get("q", "").strip().lower()
    domain_filter = request.args.get("domain", "").strip().lower()
    area_filter = request.args.get("area", "").strip()
    limit = min(int(request.args.get("limit", 50)), 200)

    results = []
    for eid, entity in _entity_cache.items():
        # Domain filter
        if domain_filter and entity.get("domain") != domain_filter:
            continue

        # Area filter
        if area_filter and entity.get("area_id") != area_filter:
            continue

        # Search query (matches entity_id and friendly_name)
        if query:
            name = entity.get("friendly_name", "").lower()
            if query not in eid.lower() and query not in name:
                continue

        results.append(entity)
        if len(results) >= limit:
            break

    # Sort: exact matches first, then alphabetical
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
    """List all entity domains with counts."""
    domain_counts: dict[str, int] = {}
    for entity in _entity_cache.values():
        domain = entity.get("domain", "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    domains = [
        {"domain": d, "count": c, "icon": _domain_icon(d)}
        for d, c in sorted(domain_counts.items())
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
    """Get entities grouped by HA area."""
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
        result.append({
            "area_id": area_id,
            "area_name": area_info.get("name", area_id),
            "entities": entities,
            "entity_count": len(entities),
        })

    return jsonify({
        "ok": True,
        "areas": result,
        "area_count": len(result),
    })


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
    }
    return icons.get(domain, "mdi:puzzle")
