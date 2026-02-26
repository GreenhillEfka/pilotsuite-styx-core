"""HomeKit zone servers API.

Provides per-Habitus-zone HomeKit server metadata with:
- automatic server generation from existing Habitus zones
- enable/disable + per-zone config updates
- stable HomeKit setup code + pairing QR endpoints
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hmac
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any

from flask import Blueprint, Response, jsonify, request

from copilot_core.api.security import (
    get_auth_token,
    is_auth_required,
    require_token,
    validate_token,
)
from copilot_core.homekit_qr import generate_qr_png_bytes, generate_qr_svg, get_zone_setup_info

homekit_bp = Blueprint("homekit", __name__, url_prefix="/api/v1/homekit")

_LOGGER = logging.getLogger(__name__)
_STORE_ENV = "PILOTSUITE_HOMEKIT_SERVERS_PATH"
_DEFAULT_STORE_PATH = "/data/homekit_zone_servers.json"
_FALLBACK_STORE_PATH = "/tmp/pilotsuite_homekit_zone_servers.json"
_LOCK = threading.RLock()
_CACHE: dict[str, Any] | None = None
_RESOLVED_STORE_PATH: Path | None = None

# 1x1 transparent PNG used only as a last-resort fallback.
_EMPTY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+tmxQAAAAASUVORK5CYII="
)

_SUPPORTED_DOMAINS = {
    "light",
    "switch",
    "cover",
    "climate",
    "fan",
    "lock",
    "media_player",
    "sensor",
    "binary_sensor",
    "input_boolean",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list_str(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                item = item.strip()
                if item:
                    out.append(item)
        return out
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _safe_zone_id(value: Any) -> str:
    zid = str(value or "").strip()
    return zid[:128]


def _safe_zone_name(value: Any, fallback: str) -> str:
    name = str(value or "").strip()
    if not name:
        return fallback
    return name[:160]


def _supported_entities(entity_ids: list[str], include_domains: list[str] | None = None) -> list[str]:
    allowed = set(include_domains or _SUPPORTED_DOMAINS)
    out: list[str] = []
    for eid in entity_ids:
        if "." not in eid:
            continue
        domain = eid.split(".", 1)[0]
        if domain in allowed and eid not in out:
            out.append(eid)
    return out


def _resolve_store_path() -> Path:
    global _RESOLVED_STORE_PATH
    if _RESOLVED_STORE_PATH is not None:
        return _RESOLVED_STORE_PATH

    configured = Path(os.environ.get(_STORE_ENV, _DEFAULT_STORE_PATH))
    candidates = [configured, Path(_FALLBACK_STORE_PATH)]
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                path.touch(exist_ok=True)
            else:
                path.write_text("", encoding="utf-8")
            _RESOLVED_STORE_PATH = path
            return path
        except Exception:
            continue

    # Last fallback in current working directory.
    fallback = Path("homekit_zone_servers.json").resolve()
    fallback.parent.mkdir(parents=True, exist_ok=True)
    fallback.touch(exist_ok=True)
    _RESOLVED_STORE_PATH = fallback
    return fallback


def _load_store() -> dict[str, Any]:
    global _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE
        path = _resolve_store_path()
        try:
            if path.exists():
                raw = path.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        servers = data.get("servers")
                        if isinstance(servers, dict):
                            _CACHE = {"servers": servers}
                            return _CACHE
        except Exception:
            _LOGGER.debug("Failed to load HomeKit servers store", exc_info=True)
        _CACHE = {"servers": {}}
        return _CACHE


def _save_store(data: dict[str, Any]) -> None:
    with _LOCK:
        path = _resolve_store_path()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        global _CACHE
        _CACHE = data


def _get_habitus_zones() -> list[dict[str, Any]]:
    """Read habitus zones from hub engine (if available)."""
    try:
        from copilot_core.hub import api as hub_api
    except Exception:
        return []

    engine = getattr(hub_api, "_zone_engine", None)
    if engine is None:
        return []

    zones: list[dict[str, Any]] = []
    try:
        overview = engine.get_overview()
        overview_zones = list(getattr(overview, "zones", []) or [])
    except Exception:
        _LOGGER.debug("Unable to access habitus overview from zone engine", exc_info=True)
        return []

    for item in overview_zones:
        if not isinstance(item, dict):
            continue
        zone_id = _safe_zone_id(item.get("zone_id"))
        if not zone_id:
            continue
        try:
            detail = engine.get_zone(zone_id) or {}
        except Exception:
            detail = {}
        entities = _as_list_str(detail.get("entities"))
        zones.append(
            {
                "zone_id": zone_id,
                "zone_name": _safe_zone_name(item.get("name"), zone_id),
                "entities": entities,
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return zones


def _new_server(zone_id: str, zone_name: str, entity_ids: list[str]) -> dict[str, Any]:
    now = _utc_now()
    setup = get_zone_setup_info(zone_id, zone_name)
    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "display_name": f"{zone_name} by Styx",
        "enabled": True,
        "entity_ids": entity_ids,
        "config": {
            "sync_entities": True,
            "include_domains": sorted(_SUPPORTED_DOMAINS),
        },
        "created_at": now,
        "updated_at": now,
        "last_seen": now,
        "setup": setup,
    }


def _sync_servers_with_zones(store: dict[str, Any]) -> dict[str, Any]:
    servers = store.setdefault("servers", {})
    zones = _get_habitus_zones()
    zone_map = {z["zone_id"]: z for z in zones}

    for zone_id, zone in zone_map.items():
        zone_name = zone["zone_name"]
        zone_entities = _supported_entities(zone["entities"])
        if zone_id not in servers:
            servers[zone_id] = _new_server(zone_id, zone_name, zone_entities)
            continue

        server = servers[zone_id]
        config = server.setdefault("config", {})
        sync_entities = bool(config.get("sync_entities", True))
        include_domains = _as_list_str(config.get("include_domains")) or sorted(_SUPPORTED_DOMAINS)

        server["zone_name"] = zone_name
        if not server.get("display_name"):
            server["display_name"] = f"{zone_name} by Styx"
        if sync_entities:
            server["entity_ids"] = _supported_entities(zone["entities"], include_domains)
        server["last_seen"] = _utc_now()
        server.setdefault("setup", get_zone_setup_info(zone_id, zone_name))
        server["setup"]["zone_name"] = zone_name

    # Mark missing zones without deleting manual history/config.
    for zone_id, server in servers.items():
        if zone_id not in zone_map:
            server["zone_missing"] = True
        else:
            server["zone_missing"] = False

    return store


def _server_status(server: dict[str, Any]) -> str:
    if not bool(server.get("enabled", False)):
        return "disabled"
    if bool(server.get("zone_missing")):
        return "degraded"
    if not _as_list_str(server.get("entity_ids")):
        return "degraded"
    return "online"


def _to_response_server(server: dict[str, Any]) -> dict[str, Any]:
    zone_id = _safe_zone_id(server.get("zone_id"))
    zone_name = _safe_zone_name(server.get("zone_name"), zone_id)
    setup = server.get("setup")
    if not isinstance(setup, dict):
        setup = get_zone_setup_info(zone_id, zone_name)
    setup_code = str(setup.get("setup_code") or "")
    uri = str(setup.get("homekit_uri") or "")
    status = _server_status(server)
    entities = _as_list_str(server.get("entity_ids"))
    return {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "display_name": _safe_zone_name(server.get("display_name"), f"{zone_name} by Styx"),
        "enabled": bool(server.get("enabled", False)),
        "status": status,
        "connectivity": {
            "zone_present": not bool(server.get("zone_missing")),
            "entity_count": len(entities),
            "pairing_ready": bool(setup_code and uri),
        },
        "entity_ids": entities,
        "entity_count": len(entities),
        "config": server.get("config", {}),
        "setup_code": setup_code,
        "homekit_uri": uri,
        "serial": str(setup.get("serial") or ""),
        "manufacturer": str(setup.get("manufacturer") or "PilotSuite"),
        "model": str(setup.get("model") or "Styx HomeKit Bridge"),
        "qr_svg_url": f"/api/v1/homekit/qr/{zone_id}.svg",
        "qr_png_url": f"/api/v1/homekit/qr/{zone_id}.png",
        "updated_at": server.get("updated_at"),
        "last_seen": server.get("last_seen"),
    }


def _summary(servers: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(servers)
    enabled = sum(1 for s in servers if s.get("enabled"))
    online = sum(1 for s in servers if s.get("status") == "online")
    degraded = sum(1 for s in servers if s.get("status") == "degraded")
    return {
        "total_servers": total,
        "enabled_servers": enabled,
        "online_servers": online,
        "degraded_servers": degraded,
    }


def get_homekit_context_for_llm() -> str:
    """Return concise HomeKit context for LLM prompt enrichment."""
    try:
        servers = _load_servers()
    except Exception:
        return ""

    enabled = [s for s in servers if bool(s.get("enabled"))]
    if not enabled:
        return ""

    zone_bits: list[str] = []
    for item in enabled[:5]:
        zone_name = _safe_zone_name(item.get("zone_name"), item.get("zone_id", "zone"))
        status = str(item.get("status", "unknown"))
        count = int(item.get("entity_count", 0) or 0)
        zone_bits.append(f"{zone_name} ({count}, {status})")

    suffix = ", ".join(zone_bits)
    if len(enabled) > 5:
        suffix += f", +{len(enabled) - 5} weitere"

    return f"HomeKit-Bridge: {len(enabled)} Zone(n) aktiv — {suffix}"


def _qr_request_authorized() -> bool:
    """Allow QR fetches with header auth or query-token fallback.

    Query fallback exists because `<img>` tags in dashboards cannot set headers.
    """
    if validate_token(request):
        return True
    if not is_auth_required():
        return True
    token = get_auth_token().strip()
    if not token:
        return True
    query_token = str(
        request.args.get("token") or request.args.get("auth_token") or ""
    ).strip()
    return bool(query_token and hmac.compare_digest(query_token, token))


def _load_servers() -> list[dict[str, Any]]:
    store = _load_store()
    synced = _sync_servers_with_zones(store)
    _save_store(synced)
    servers_raw = list((synced.get("servers") or {}).values())
    servers = [_to_response_server(server) for server in servers_raw if isinstance(server, dict)]
    servers.sort(key=lambda item: (item.get("zone_name") or item.get("zone_id") or "").lower())
    return servers


def sync_homekit_from_habitus_zones() -> dict[str, Any]:
    """Public helper for other modules to trigger HomeKit sync."""
    store = _load_store()
    synced = _sync_servers_with_zones(store)
    _save_store(synced)
    servers = _load_servers()
    return {"ok": True, "summary": _summary(servers), "server_count": len(servers)}


def _set_server_config(zone_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    store = _load_store()
    synced = _sync_servers_with_zones(store)
    servers = synced.setdefault("servers", {})
    server = servers.get(zone_id)
    if not isinstance(server, dict):
        return None

    if "zone_name" in patch:
        server["zone_name"] = _safe_zone_name(patch.get("zone_name"), zone_id)
    if "display_name" in patch:
        server["display_name"] = _safe_zone_name(
            patch.get("display_name"),
            f"{_safe_zone_name(server.get('zone_name'), zone_id)} by Styx",
        )
    if "enabled" in patch:
        server["enabled"] = bool(patch.get("enabled"))
    if "entity_ids" in patch:
        cfg = server.setdefault("config", {})
        include_domains = _as_list_str(cfg.get("include_domains")) or sorted(_SUPPORTED_DOMAINS)
        server["entity_ids"] = _supported_entities(_as_list_str(patch.get("entity_ids")), include_domains)
    config_patch = patch.get("config")
    if isinstance(config_patch, dict):
        cfg = server.setdefault("config", {})
        cfg.update(config_patch)
        include_domains = _as_list_str(cfg.get("include_domains")) or sorted(_SUPPORTED_DOMAINS)
        cfg["include_domains"] = include_domains
        if cfg.get("sync_entities"):
            zone_map = {z["zone_id"]: z for z in _get_habitus_zones()}
            zone = zone_map.get(zone_id)
            if zone:
                server["entity_ids"] = _supported_entities(zone.get("entities", []), include_domains)

    zone_name = _safe_zone_name(server.get("zone_name"), zone_id)
    server["setup"] = get_zone_setup_info(zone_id, zone_name)
    server["updated_at"] = _utc_now()
    _save_store(synced)
    return _to_response_server(server)


@homekit_bp.route("", methods=["GET"])
@homekit_bp.route("/status", methods=["GET"])
@require_token
def homekit_status() -> Response:
    servers = _load_servers()
    return jsonify({"ok": True, "summary": _summary(servers), "servers": servers})


@homekit_bp.route("/servers", methods=["GET"])
@require_token
def list_servers() -> Response:
    servers = _load_servers()
    return jsonify({"ok": True, "servers": servers, "summary": _summary(servers)})


@homekit_bp.route("/servers/<zone_id>", methods=["GET"])
@require_token
def get_server(zone_id: str) -> Response:
    zone_id = _safe_zone_id(zone_id)
    if not zone_id:
        return jsonify({"ok": False, "error": "invalid_zone_id"}), 400
    for server in _load_servers():
        if server.get("zone_id") == zone_id:
            return jsonify({"ok": True, "server": server})
    return jsonify({"ok": False, "error": "zone_not_found"}), 404


@homekit_bp.route("/toggle", methods=["POST"])
@require_token
def toggle_server() -> Response:
    body = request.get_json(silent=True) or {}
    zone_id = _safe_zone_id(body.get("zone_id"))
    if not zone_id:
        return jsonify({"success": False, "error": "zone_id_required"}), 400

    enabled_value = body.get("enabled")
    enabled = bool(enabled_value) if enabled_value is not None else True
    entity_ids = _as_list_str(body.get("entity_ids"))
    zone_name = _safe_zone_name(body.get("zone_name"), zone_id)

    store = _load_store()
    synced = _sync_servers_with_zones(store)
    servers = synced.setdefault("servers", {})
    if zone_id not in servers:
        servers[zone_id] = _new_server(zone_id, zone_name, _supported_entities(entity_ids))

    patch: dict[str, Any] = {
        "enabled": enabled,
    }
    if entity_ids:
        patch["entity_ids"] = entity_ids
    if zone_name:
        patch["zone_name"] = zone_name
    response = _set_server_config(zone_id, patch)
    if response is None:
        return jsonify({"success": False, "error": "zone_not_found"}), 404

    return jsonify(
        {
            "success": True,
            "zone_id": response["zone_id"],
            "zone_name": response["zone_name"],
            "enabled": response["enabled"],
            "status": response["status"],
            "entities_exposed": response["entity_count"],
            "server": response,
        }
    )


@homekit_bp.route("/servers/<zone_id>/config", methods=["POST"])
@require_token
def configure_server(zone_id: str) -> Response:
    zone_id = _safe_zone_id(zone_id)
    if not zone_id:
        return jsonify({"ok": False, "error": "invalid_zone_id"}), 400
    body = request.get_json(silent=True) or {}
    patch: dict[str, Any] = {}
    if "enabled" in body:
        patch["enabled"] = bool(body.get("enabled"))
    if "display_name" in body:
        patch["display_name"] = body.get("display_name")
    if "zone_name" in body:
        patch["zone_name"] = body.get("zone_name")
    if "entity_ids" in body:
        patch["entity_ids"] = _as_list_str(body.get("entity_ids"))

    cfg_patch: dict[str, Any] = {}
    if "sync_entities" in body:
        cfg_patch["sync_entities"] = bool(body.get("sync_entities"))
    if "include_domains" in body:
        include_domains = [d for d in _as_list_str(body.get("include_domains")) if d in _SUPPORTED_DOMAINS]
        cfg_patch["include_domains"] = include_domains or sorted(_SUPPORTED_DOMAINS)
    if cfg_patch:
        patch["config"] = cfg_patch

    updated = _set_server_config(zone_id, patch)
    if updated is None:
        return jsonify({"ok": False, "error": "zone_not_found"}), 404
    return jsonify({"ok": True, "server": updated})


@homekit_bp.route("/sync", methods=["POST"])
@require_token
def sync_servers() -> Response:
    store = _load_store()
    synced = _sync_servers_with_zones(store)
    _save_store(synced)
    servers = _load_servers()
    return jsonify({"ok": True, "summary": _summary(servers), "servers": servers})


@homekit_bp.route("/all-zones-info", methods=["GET"])
@require_token
def all_zones_info() -> Response:
    servers = _load_servers()
    zones = []
    for server in servers:
        zones.append(
            {
                "zone_id": server["zone_id"],
                "zone_name": server["zone_name"],
                "display_name": server["display_name"],
                "enabled": server["enabled"],
                "status": server["status"],
                "entity_count": server["entity_count"],
                "setup_code": server["setup_code"],
                "homekit_uri": server["homekit_uri"],
                "serial": server["serial"],
                "manufacturer": server["manufacturer"],
                "model": server["model"],
                "qr_svg_url": f"/api/v1/homekit/qr/{server['zone_id']}.svg",
                "qr_png_url": f"/api/v1/homekit/qr/{server['zone_id']}.png",
            }
        )
    return jsonify({"ok": True, "zones": zones, "summary": _summary(servers)})


@homekit_bp.route("/qr/<zone_id>.svg", methods=["GET"])
def qr_svg(zone_id: str) -> Response:
    if not _qr_request_authorized():
        return jsonify({"ok": False, "error": "Authentication required"}), 401
    zone_id = _safe_zone_id(zone_id)
    if not zone_id:
        return jsonify({"ok": False, "error": "invalid_zone_id"}), 400
    servers = {s["zone_id"]: s for s in _load_servers()}
    zone_name = servers.get(zone_id, {}).get("zone_name", zone_id)
    svg = generate_qr_svg(zone_id, zone_name=str(zone_name))
    if not svg:
        # readable fallback (still useful in UI diagnostics)
        info = get_zone_setup_info(zone_id, str(zone_name))
        uri = info.get("homekit_uri", "")
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'>"
            "<rect width='100%' height='100%' fill='white'/>"
            "<text x='20' y='40' font-size='14' fill='black'>HomeKit QR unavailable</text>"
            f"<text x='20' y='70' font-size='10' fill='black'>{uri}</text>"
            "</svg>"
        )
    return Response(svg, mimetype="image/svg+xml")


@homekit_bp.route("/qr/<zone_id>.png", methods=["GET"])
def qr_png(zone_id: str) -> Response:
    if not _qr_request_authorized():
        return jsonify({"ok": False, "error": "Authentication required"}), 401
    zone_id = _safe_zone_id(zone_id)
    if not zone_id:
        return jsonify({"ok": False, "error": "invalid_zone_id"}), 400
    servers = {s["zone_id"]: s for s in _load_servers()}
    zone_name = servers.get(zone_id, {}).get("zone_name", zone_id)
    png = generate_qr_png_bytes(zone_id, zone_name=str(zone_name))
    if png:
        if png.lstrip().startswith(b"<svg"):
            return Response(png, mimetype="image/svg+xml")
        return Response(png, mimetype="image/png")
    return Response(_EMPTY_PNG, mimetype="image/png")
