"""HA Bridge API — Discover HA entities/areas/devices from within the Core Add-on.

The Core Add-on runs inside HA's Supervisor environment with access to:
  - SUPERVISOR_TOKEN (env var) for authenticated API calls
  - http://supervisor/core/api/ (Supervisor proxy to HA REST API)
  - ws://homeassistant.local.hass.io:8123/api/websocket (direct HA WebSocket)

This bridge fetches all HA data and feeds it into the entity search cache,
eliminating the need for the HA integration to push data separately.

Endpoints:
  POST /api/v1/ha/discover       — Trigger full HA discovery (REST + WebSocket)
  GET  /api/v1/ha/status         — Bridge status (last sync, counts)

Data collected:
  - REST /api/states: entity states + attributes
  - REST /api/config: HA config (name, version, components)
  - REST /api/services: available service domains
  - REST /api/hassio/addons: installed add-ons
  - WS config/entity_registry/list: entity → area_id, device_id, labels, platform
  - WS config/device_registry/list: device → manufacturer, model, area_id
  - WS config/area_registry/list: area → name, floor_id, icon
  - WS config/floor_registry/list: floor → name, level
  - WS config/label_registry/list: labels

Note: area_id is NOT in /api/states. It only comes from the entity/device registries
which are only accessible via WebSocket API (or HA internals).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from typing import Any

import requests
from flask import Blueprint, jsonify, request as flask_request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

ha_bridge_bp = Blueprint("ha_bridge", __name__, url_prefix="/api/v1/ha")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SUPERVISOR_API = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
_EXTERNAL_HA_API = os.environ.get(
    "HOME_ASSISTANT_URL",
    os.environ.get("HA_URL", "http://homeassistant.local:8123"),
).rstrip("/")

# WebSocket URLs to try in order
_WS_URLS = [
    "ws://homeassistant.local.hass.io:8123/api/websocket",
    "ws://supervisor/core/websocket",
    "ws://homeassistant:8123/api/websocket",
    "ws://localhost:8123/api/websocket",
]

# State
_last_discovery: dict[str, Any] = {}
_discovery_lock = threading.Lock()


def _get_token() -> str:
    """Get the best available auth token."""
    return (
        os.environ.get("SUPERVISOR_TOKEN", "").strip()
        or os.environ.get("HOME_ASSISTANT_TOKEN", "").strip()
        or os.environ.get("HA_TOKEN", "").strip()
    )


# ---------------------------------------------------------------------------
# REST API helpers
# ---------------------------------------------------------------------------

def _ha_rest_get(path: str, timeout: int = 15) -> dict | list | None:
    """GET request to HA REST API via Supervisor proxy, with external fallback."""
    token = _get_token()
    if not token:
        _LOGGER.warning("No HA token available for bridge")
        return None

    headers = {"Authorization": f"Bearer {token}"}

    # Try Supervisor proxy first (most reliable from within add-on)
    for base_url in [_SUPERVISOR_API, f"{_EXTERNAL_HA_API}/api"]:
        url = f"{base_url.rstrip('/')}{path}" if not path.startswith("/api") else f"{base_url.rstrip('/api')}{path}"
        # Normalize URL
        if base_url == _SUPERVISOR_API:
            url = f"{_SUPERVISOR_API}{path}"
        else:
            url = f"{_EXTERNAL_HA_API}{path}"
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.ok:
                return resp.json()
        except Exception:
            continue

    _LOGGER.debug("REST GET %s failed on all endpoints", path)
    return None


# ---------------------------------------------------------------------------
# WebSocket registry fetch
# ---------------------------------------------------------------------------

async def _ws_fetch_registries(token: str) -> dict[str, list]:
    """Connect to HA WebSocket and fetch all registry data."""
    registries: dict[str, list] = {
        "entity_registry": [],
        "device_registry": [],
        "area_registry": [],
        "floor_registry": [],
        "label_registry": [],
    }

    try:
        import websockets
    except ImportError:
        _LOGGER.warning("websockets not installed — registry fetch unavailable")
        return registries

    commands = [
        (1, "config/entity_registry/list", "entity_registry"),
        (2, "config/device_registry/list", "device_registry"),
        (3, "config/area_registry/list", "area_registry"),
        (4, "config/floor_registry/list", "floor_registry"),
        (5, "config/label_registry/list", "label_registry"),
    ]

    for ws_url in _WS_URLS:
        try:
            async with websockets.connect(ws_url, open_timeout=5) as ws:
                # Auth handshake
                auth_req = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if auth_req.get("type") != "auth_required":
                    continue

                await ws.send(json.dumps({"type": "auth", "access_token": token}))
                auth_resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if auth_resp.get("type") != "auth_ok":
                    _LOGGER.debug("WS auth failed at %s", ws_url)
                    continue

                _LOGGER.info("HA Bridge: WebSocket connected to %s", ws_url)

                # Fetch all registries
                for msg_id, cmd, key in commands:
                    await ws.send(json.dumps({"id": msg_id, "type": cmd}))
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    resp = json.loads(raw)
                    if resp.get("success"):
                        result = resp.get("result", [])
                        registries[key] = result
                        _LOGGER.debug("  %s: %d entries", key, len(result))

                return registries  # Success — stop trying other URLs

        except Exception as e:
            _LOGGER.debug("WS %s failed: %s", ws_url, e)
            continue

    _LOGGER.warning("WebSocket registry fetch failed on all endpoints")
    return registries


def _run_ws_fetch(token: str) -> dict[str, list]:
    """Run async WebSocket fetch in a new event loop (safe from sync Flask)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_ws_fetch_registries(token))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Discovery logic
# ---------------------------------------------------------------------------

def _run_full_discovery() -> dict[str, Any]:
    """Execute full HA discovery: REST + WebSocket."""
    global _last_discovery
    token = _get_token()

    result: dict[str, Any] = {
        "timestamp": time.time(),
        "token_available": bool(token),
        "rest": {},
        "ws": {},
        "entities": 0,
        "areas": 0,
        "devices": 0,
        "errors": [],
    }

    if not token:
        result["errors"].append("No auth token available")
        _last_discovery = result
        return result

    # --- REST API ---
    _LOGGER.info("HA Bridge: Starting REST discovery...")

    states = _ha_rest_get("/states")
    if states and isinstance(states, list):
        result["rest"]["states"] = len(states)
    else:
        states = []
        result["errors"].append("REST /states failed")

    config = _ha_rest_get("/config")
    if config:
        result["rest"]["config"] = {
            "location_name": config.get("location_name", ""),
            "version": config.get("version", ""),
            "components_count": len(config.get("components", [])),
        }

    services = _ha_rest_get("/services")
    if services and isinstance(services, list):
        result["rest"]["services"] = len(services)

    addons = _ha_rest_get("/hassio/addons")
    if addons and isinstance(addons, dict):
        addon_list = addons.get("data", {}).get("addons", [])
        result["rest"]["addons"] = len(addon_list)

    # --- WebSocket registries ---
    _LOGGER.info("HA Bridge: Starting WebSocket registry discovery...")
    registries = _run_ws_fetch(token)

    states_by_id = {s.get("entity_id", ""): s for s in states}
    area_map = {a.get("area_id", ""): a for a in registries["area_registry"]}
    device_map = {d.get("id", ""): d for d in registries["device_registry"]}

    result["ws"] = {
        k: len(v) for k, v in registries.items()
    }

    # --- Build enriched entity list ---
    entities = []
    for reg_entry in registries.get("entity_registry", []):
        eid = reg_entry.get("entity_id", "")
        if not eid or reg_entry.get("disabled_by"):
            continue

        domain = eid.split(".")[0] if "." in eid else ""
        state_obj = states_by_id.get(eid, {})
        attrs = state_obj.get("attributes", {}) if state_obj else {}

        # Area resolution: entity → device → area
        area_id = reg_entry.get("area_id", "")
        device_id = reg_entry.get("device_id", "")
        if not area_id and device_id:
            device = device_map.get(device_id, {})
            area_id = device.get("area_id", "")

        area_name = area_map.get(area_id, {}).get("name", "")
        friendly_name = attrs.get("friendly_name", reg_entry.get("name", eid))

        device_info = {}
        if device_id and device_id in device_map:
            dev = device_map[device_id]
            device_info = {
                "device_id": device_id,
                "device_name": dev.get("name_by_user") or dev.get("name", ""),
                "manufacturer": dev.get("manufacturer", ""),
                "model": dev.get("model", ""),
                "sw_version": dev.get("sw_version", ""),
            }

        entities.append({
            "entity_id": eid,
            "domain": domain,
            "state": state_obj.get("state", "unknown") if state_obj else "unavailable",
            "friendly_name": friendly_name,
            "device_class": reg_entry.get("original_device_class", "") or attrs.get("device_class", ""),
            "area_id": area_id,
            "area_name": area_name,
            "icon": reg_entry.get("icon", "") or attrs.get("icon", ""),
            "unit_of_measurement": reg_entry.get("unit_of_measurement", "") or attrs.get("unit_of_measurement", ""),
            "platform": reg_entry.get("platform", ""),
            "labels": reg_entry.get("labels", []),
            "device": device_info,
        })

    # Build area list
    areas = [
        {
            "area_id": a.get("area_id", ""),
            "name": a.get("name", ""),
            "floor_id": a.get("floor_id", ""),
            "icon": a.get("icon", ""),
            "labels": a.get("labels", []),
        }
        for a in registries.get("area_registry", [])
    ]

    # Build device list
    devices = [
        {
            "device_id": d.get("id", ""),
            "name": d.get("name_by_user") or d.get("name", ""),
            "manufacturer": d.get("manufacturer", ""),
            "model": d.get("model", ""),
            "sw_version": d.get("sw_version", ""),
            "area_id": d.get("area_id", ""),
            "labels": d.get("labels", []),
        }
        for d in registries.get("device_registry", [])
        if not d.get("disabled_by")
    ]

    # --- Feed into entity search cache ---
    try:
        from copilot_core.api.v1.entity_search import (
            update_entity_cache,
            update_area_cache,
            update_device_cache,
            _entity_cache,
        )

        # Use bulk-style update (entity_search handles role inference)
        for entity in entities:
            eid = entity["entity_id"]
            _entity_cache[eid] = {
                **entity,
                "roles": [],  # Will be inferred below
            }

        # Re-import and call the proper role-inferring function
        from copilot_core.api.v1.entity_search import _infer_roles
        for eid, cached in _entity_cache.items():
            cached["roles"] = _infer_roles(
                eid,
                cached.get("friendly_name", ""),
                cached.get("device_class", ""),
            )

        update_area_cache(areas)
        update_device_cache(devices)

        _LOGGER.info(
            "HA Bridge: Fed %d entities, %d areas, %d devices into search cache",
            len(entities), len(areas), len(devices),
        )
    except Exception as e:
        _LOGGER.warning("Failed to feed discovery into entity search: %s", e)
        result["errors"].append(f"cache_feed: {e}")

    # --- Persist to /data ---
    try:
        persist_data = {
            "timestamp": result["timestamp"],
            "entities": entities,
            "areas": areas,
            "devices": devices,
        }
        with open("/data/ha_discovery.json", "w") as f:
            json.dump(persist_data, f, default=str)
        _LOGGER.debug("HA Bridge: Saved discovery to /data/ha_discovery.json")
    except Exception:
        pass  # Non-critical

    result["entities"] = len(entities)
    result["areas"] = len(areas)
    result["devices"] = len(devices)

    _last_discovery = result
    return result


# ---------------------------------------------------------------------------
# Flask endpoints
# ---------------------------------------------------------------------------

@ha_bridge_bp.route("/discover", methods=["POST"])
@require_token
def trigger_discovery():
    """Trigger full HA discovery (REST + WebSocket).

    Fetches all entities, areas, devices from HA and feeds them
    into the entity search cache. Can be called manually or on
    add-on startup.
    """
    with _discovery_lock:
        result = _run_full_discovery()

    return jsonify({
        "ok": len(result.get("errors", [])) == 0,
        "entities": result.get("entities", 0),
        "areas": result.get("areas", 0),
        "devices": result.get("devices", 0),
        "rest": result.get("rest", {}),
        "ws": result.get("ws", {}),
        "errors": result.get("errors", []),
        "timestamp": result.get("timestamp", 0),
    })


@ha_bridge_bp.route("/status", methods=["GET"])
@require_token
def bridge_status():
    """Get HA Bridge status — last discovery result."""
    token = _get_token()
    return jsonify({
        "ok": True,
        "token_available": bool(token),
        "supervisor_api": _SUPERVISOR_API,
        "external_ha_api": _EXTERNAL_HA_API,
        "last_discovery": {
            "timestamp": _last_discovery.get("timestamp", 0),
            "entities": _last_discovery.get("entities", 0),
            "areas": _last_discovery.get("areas", 0),
            "devices": _last_discovery.get("devices", 0),
            "errors": _last_discovery.get("errors", []),
        } if _last_discovery else None,
    })


@ha_bridge_bp.route("/export", methods=["GET"])
@require_token
def export_discovery():
    """Download the last discovery result as JSON file.

    Returns /data/ha_discovery.json if it exists, otherwise runs a fresh
    discovery and returns the result.

    The file is saved at: /data/ha_discovery.json (inside the add-on volume).
    """
    from flask import send_file
    import io

    discovery_path = "/data/ha_discovery.json"

    # If file doesn't exist, run discovery first
    if not os.path.exists(discovery_path):
        with _discovery_lock:
            _run_full_discovery()

    if os.path.exists(discovery_path):
        return send_file(
            discovery_path,
            mimetype="application/json",
            as_attachment=True,
            download_name="ha_discovery.json",
        )

    return jsonify({"ok": False, "error": "No discovery data available"}), 404


# ---------------------------------------------------------------------------
# Auto-discovery on startup (called from core_setup)
# ---------------------------------------------------------------------------

def auto_discover_on_startup() -> None:
    """Run discovery in background thread on add-on startup.

    Called by core_setup.py after all blueprints are registered.
    Waits 10 seconds to let HA finish loading before fetching.
    """
    token = _get_token()
    if not token:
        _LOGGER.info("HA Bridge: No token — skipping auto-discovery")
        return

    def _delayed_discover():
        time.sleep(10)  # Let HA settle
        _LOGGER.info("HA Bridge: Starting auto-discovery...")
        with _discovery_lock:
            result = _run_full_discovery()
        _LOGGER.info(
            "HA Bridge auto-discovery: %d entities, %d areas, %d devices, %d errors",
            result.get("entities", 0),
            result.get("areas", 0),
            result.get("devices", 0),
            len(result.get("errors", [])),
        )

    thread = threading.Thread(target=_delayed_discover, daemon=True, name="ha-bridge-auto")
    thread.start()
