"""Habitus Zones API - Bidirektionaler Zonen-Sync zwischen HA und Core.

Endpunkte:
  POST /api/v1/habitus/zones/sync     HA → Core: Zonen synchronisieren
  GET  /api/v1/habitus/zones           Alle Zonen abrufen
  GET  /api/v1/habitus/zones/<zone_id> Einzelne Zone abrufen
  PUT  /api/v1/habitus/zones/<zone_id> Zone aktualisieren
  DELETE /api/v1/habitus/zones/<zone_id> Zone loeschen

Speicherung: /data/habitus_zones.json (persistent)
EventBus: Publiziert zone.* Events fuer inter-modul Kommunikation
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

habitus_zones_bp = Blueprint("habitus_zones", __name__, url_prefix="/api/v1/habitus/zones")

_ZONES_FILE = "/data/habitus_zones.json"
_zones_lock = threading.Lock()
_zones_cache: Dict[str, Dict[str, Any]] = {}
_event_bus = None


def init_habitus_zones_api(event_bus=None) -> None:
    """Initialize the Habitus Zones API with EventBus reference."""
    global _event_bus
    _event_bus = event_bus
    _load_zones()
    _LOGGER.info("Habitus Zones API initialized (%d zones loaded)", len(_zones_cache))


def _load_zones() -> None:
    """Load zones from persistent storage."""
    global _zones_cache
    try:
        if os.path.exists(_ZONES_FILE):
            with open(_ZONES_FILE, "r") as f:
                data = json.load(f)
            _zones_cache = {z["zone_id"]: z for z in data.get("zones", []) if "zone_id" in z}
            _LOGGER.debug("Loaded %d zones from %s", len(_zones_cache), _ZONES_FILE)
        else:
            _zones_cache = {}
    except Exception:
        _LOGGER.exception("Failed to load zones from %s", _ZONES_FILE)
        _zones_cache = {}


def _save_zones() -> None:
    """Persist zones to disk."""
    try:
        os.makedirs(os.path.dirname(_ZONES_FILE), exist_ok=True)
        zones_list = list(_zones_cache.values())
        with open(_ZONES_FILE, "w") as f:
            json.dump({
                "zones": zones_list,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(zones_list),
            }, f, indent=2, ensure_ascii=False)
        _LOGGER.debug("Saved %d zones to %s", len(zones_list), _ZONES_FILE)
    except Exception:
        _LOGGER.exception("Failed to save zones to %s", _ZONES_FILE)


def _publish(topic: str, data: Dict[str, Any]) -> None:
    """Publish event to EventBus if available."""
    if _event_bus:
        try:
            _event_bus.publish(topic, data, source="habitus_zones_api")
        except Exception:
            _LOGGER.debug("EventBus publish failed for %s", topic)


def get_all_zones() -> List[Dict[str, Any]]:
    """Get all zones (for internal module use)."""
    with _zones_lock:
        return list(_zones_cache.values())


def get_zone(zone_id: str) -> Optional[Dict[str, Any]]:
    """Get a single zone by ID (for internal module use)."""
    with _zones_lock:
        return _zones_cache.get(zone_id)


# --- REST Endpoints ---


@habitus_zones_bp.route("/sync", methods=["POST"])
@require_token
def sync_zones():
    """HA → Core: Synchronize all zones from HA integration.

    Payload: { "zones": [{ "zone_id": "zone:wohnzimmer", "name": "...", ... }] }
    """
    body = request.get_json(silent=True) or {}
    incoming_zones = body.get("zones", [])

    if not isinstance(incoming_zones, list):
        return jsonify({"ok": False, "error": "zones must be a list"}), 400

    synced = []
    with _zones_lock:
        # Track which zones were synced to detect deletions
        synced_ids = set()
        for zone_data in incoming_zones:
            zone_id = zone_data.get("zone_id")
            if not zone_id:
                continue

            # Merge with existing data (keep Core-side metadata)
            existing = _zones_cache.get(zone_id, {})
            merged = {
                **existing,
                **zone_data,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "source": "ha",
            }
            _zones_cache[zone_id] = merged
            synced_ids.add(zone_id)
            synced.append(zone_id)

        # Remove zones that HA no longer has (if full sync)
        if body.get("full_sync", False):
            removed = [zid for zid in _zones_cache if zid not in synced_ids]
            for zid in removed:
                del _zones_cache[zid]
                _publish("zone.deleted", {"zone_id": zid})

        _save_zones()

    _publish("zone.synced", {"zone_ids": synced, "count": len(synced)})

    return jsonify({
        "ok": True,
        "synced": len(synced),
        "zone_ids": synced,
    })


@habitus_zones_bp.route("", methods=["GET"])
@require_token
def list_zones():
    """Get all habitus zones."""
    with _zones_lock:
        zones = list(_zones_cache.values())

    # Optional filtering
    zone_type = request.args.get("type")
    if zone_type:
        zones = [z for z in zones if z.get("zone_type") == zone_type]

    return jsonify({
        "ok": True,
        "zones": zones,
        "count": len(zones),
    })


@habitus_zones_bp.route("/<zone_id>", methods=["GET"])
@require_token
def get_zone_endpoint(zone_id: str):
    """Get a single zone."""
    zone_id = zone_id if zone_id.startswith("zone:") else f"zone:{zone_id}"
    with _zones_lock:
        zone = _zones_cache.get(zone_id)

    if zone is None:
        return jsonify({"ok": False, "error": "Zone not found"}), 404

    return jsonify({"ok": True, "zone": zone})


@habitus_zones_bp.route("/<zone_id>", methods=["PUT"])
@require_token
def update_zone(zone_id: str):
    """Update a zone (from Core-side or HA)."""
    zone_id = zone_id if zone_id.startswith("zone:") else f"zone:{zone_id}"
    body = request.get_json(silent=True) or {}

    with _zones_lock:
        existing = _zones_cache.get(zone_id)
        if existing is None:
            return jsonify({"ok": False, "error": "Zone not found"}), 404

        merged = {
            **existing,
            **body,
            "zone_id": zone_id,  # Prevent overwriting zone_id
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _zones_cache[zone_id] = merged
        _save_zones()

    _publish("zone.updated", {"zone_id": zone_id, "zone": merged})

    return jsonify({"ok": True, "zone": merged})


@habitus_zones_bp.route("/<zone_id>", methods=["DELETE"])
@require_token
def delete_zone(zone_id: str):
    """Delete a zone."""
    zone_id = zone_id if zone_id.startswith("zone:") else f"zone:{zone_id}"

    with _zones_lock:
        if zone_id not in _zones_cache:
            return jsonify({"ok": False, "error": "Zone not found"}), 404

        del _zones_cache[zone_id]
        _save_zones()

    _publish("zone.deleted", {"zone_id": zone_id})

    return jsonify({"ok": True, "deleted": zone_id})


@habitus_zones_bp.route("/summary", methods=["GET"])
@require_token
def zones_summary():
    """Get a summary of all zones with mood and activity data."""
    with _zones_lock:
        zones = list(_zones_cache.values())

    summary = []
    for zone in zones:
        summary.append({
            "zone_id": zone.get("zone_id"),
            "name": zone.get("name"),
            "entity_count": len(zone.get("entity_ids", [])),
            "roles": list((zone.get("entities") or {}).keys()),
            "synced_at": zone.get("synced_at"),
            "source": zone.get("source", "unknown"),
        })

    return jsonify({
        "ok": True,
        "zones": summary,
        "count": len(summary),
    })
