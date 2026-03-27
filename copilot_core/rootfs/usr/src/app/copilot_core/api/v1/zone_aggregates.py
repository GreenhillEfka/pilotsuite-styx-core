"""Zone Aggregates API — Device-class-aware entity aggregation + zone scene management.

Provides aggregated entity views (Sammelentitaeten) per zone and
zone-specific scene capture/apply/preset endpoints.

Endpoints:
  GET  /api/v1/zone/aggregates/<zone_id>                - Aggregated entities
  GET  /api/v1/zone/aggregates/<zone_id>/presets         - Zone-specific presets
  GET  /api/v1/zone/aggregates/categories                - All aggregate categories
  POST /api/v1/zone/aggregates/<zone_id>/scene/capture   - Capture zone as HA scene
  POST /api/v1/zone/aggregates/<zone_id>/scene/apply     - Apply saved scene
  GET  /api/v1/zone/aggregates/<zone_id>/scenes          - List zone scenes
  DELETE /api/v1/zone/aggregates/<zone_id>/scene/<sid>   - Delete zone scene
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests as http_requests
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

zone_aggregates_bp = Blueprint(
    "zone_aggregates", __name__, url_prefix="/api/v1/zone/aggregates",
)

_svc: dict[str, Any] = {}
_aggregator = None
_scene_db: str = ""


def _normalize_entities_by_role(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for role, raw_entities in value.items():
        if isinstance(raw_entities, list):
            items = [str(eid).strip() for eid in raw_entities if str(eid).strip()]
            if items:
                normalized[str(role)] = items
    return normalized



def _normalize_entity_ids(zone: dict[str, Any]) -> list[str]:
    raw_entity_ids = zone.get("entity_ids")
    if isinstance(raw_entity_ids, list):
        entity_ids = [str(eid).strip() for eid in raw_entity_ids if str(eid).strip()]
    else:
        raw_entities = zone.get("entities")
        if isinstance(raw_entities, list):
            entity_ids = [str(eid).strip() for eid in raw_entities if str(eid).strip()]
        elif isinstance(raw_entities, dict):
            entity_ids = [
                str(eid).strip()
                for role_entities in raw_entities.values()
                if isinstance(role_entities, list)
                for eid in role_entities
                if str(eid).strip()
            ]
        else:
            entity_ids = []

    return list(dict.fromkeys(entity_ids))



def _merge_entities_by_role(*entity_maps: Any) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for entity_map in entity_maps:
        for role, entity_ids in _normalize_entities_by_role(entity_map).items():
            bucket = merged.setdefault(role, [])
            for eid in entity_ids:
                if eid not in bucket:
                    bucket.append(eid)
    return merged



def init_zone_aggregates_api(aggregator=None, **services: Any) -> None:
    """Initialize Zone Aggregates API."""
    global _aggregator, _scene_db
    _svc.clear()
    _svc.update(services)
    _aggregator = aggregator
    _scene_db = os.path.join(
        os.environ.get("DATA_DIR", "/data"),
        "zone_scenes.sqlite3",
    )
    _init_scene_db()
    logger.info("Zone Aggregates API initialized (aggregator=%s)", aggregator is not None)


# ── Persistent Scene Storage (SQLite) ───────────────────────────────────

def _get_scene_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_scene_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_scene_db():
    """Create scene storage table if not exists."""
    if not _scene_db:
        return
    conn = None
    try:
        os.makedirs(os.path.dirname(_scene_db) or ".", exist_ok=True)
        conn = _get_scene_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS zone_scenes (
                scene_id     TEXT PRIMARY KEY,
                zone_id      TEXT NOT NULL,
                zone_name    TEXT NOT NULL DEFAULT '',
                name         TEXT NOT NULL,
                entity_states TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL,
                applied_count INTEGER NOT NULL DEFAULT 0,
                last_applied REAL,
                source       TEXT NOT NULL DEFAULT 'manual',
                is_favorite  INTEGER NOT NULL DEFAULT 0,
                ha_scene_entity_id TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_zone_scenes_zone
            ON zone_scenes(zone_id)
        """)
        conn.commit()
        logger.info("Zone scene DB initialized: %s", _scene_db)
    except Exception:
        logger.exception("Failed to init zone scene DB")
    finally:
        if conn is not None:
            conn.close()


def _save_scene(scene: dict[str, Any]) -> bool:
    """Persist a scene to SQLite."""
    conn = None
    try:
        conn = _get_scene_conn()
        conn.execute("""
            INSERT OR REPLACE INTO zone_scenes
            (scene_id, zone_id, zone_name, name, entity_states, created_at,
             applied_count, last_applied, source, is_favorite, ha_scene_entity_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scene["scene_id"],
            scene["zone_id"],
            scene.get("zone_name", ""),
            scene["name"],
            json.dumps(scene.get("entity_states", {})),
            scene.get("created_at", time.time()),
            scene.get("applied_count", 0),
            scene.get("last_applied"),
            scene.get("source", "manual"),
            1 if scene.get("is_favorite") else 0,
            scene.get("ha_scene_entity_id"),
        ))
        conn.commit()
        return True
    except Exception:
        logger.exception("Failed to save scene %s", scene.get("scene_id"))
        return False
    finally:
        if conn is not None:
            conn.close()


def _load_zone_scenes(zone_id: str) -> list[dict[str, Any]]:
    """Load all scenes for a zone from SQLite."""
    conn = None
    try:
        conn = _get_scene_conn()
        rows = conn.execute(
            "SELECT * FROM zone_scenes WHERE zone_id = ? ORDER BY created_at DESC",
            (zone_id,),
        ).fetchall()
        return [_row_to_scene(r) for r in rows]
    except Exception:
        logger.debug("Failed to load scenes for zone %s", zone_id)
        return []
    finally:
        if conn is not None:
            conn.close()


def _load_scene(scene_id: str) -> dict[str, Any] | None:
    """Load a single scene by ID."""
    conn = None
    try:
        conn = _get_scene_conn()
        row = conn.execute(
            "SELECT * FROM zone_scenes WHERE scene_id = ?", (scene_id,),
        ).fetchone()
        return _row_to_scene(row) if row else None
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()


def _delete_scene(scene_id: str) -> bool:
    """Delete a scene from SQLite."""
    conn = None
    try:
        conn = _get_scene_conn()
        conn.execute("DELETE FROM zone_scenes WHERE scene_id = ?", (scene_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def _increment_apply_count(scene_id: str) -> None:
    """Increment apply count and set last_applied timestamp."""
    conn = None
    try:
        conn = _get_scene_conn()
        conn.execute(
            "UPDATE zone_scenes SET applied_count = applied_count + 1, last_applied = ? WHERE scene_id = ?",
            (time.time(), scene_id),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        if conn is not None:
            conn.close()


def _row_to_scene(row) -> dict[str, Any]:
    """Convert SQLite row to scene dict."""
    return {
        "scene_id": row["scene_id"],
        "zone_id": row["zone_id"],
        "zone_name": row["zone_name"],
        "name": row["name"],
        "entity_states": json.loads(row["entity_states"]),
        "created_at": row["created_at"],
        "applied_count": row["applied_count"],
        "last_applied": row["last_applied"],
        "source": row["source"],
        "is_favorite": bool(row["is_favorite"]),
        "ha_scene_entity_id": row["ha_scene_entity_id"],
    }


# ── Zone Helpers ────────────────────────────────────────────────────────

def _get_zone(zone_id: str) -> dict[str, Any] | None:
    """Get zone config by ID, preferring the Core truth engine."""
    requested_ids = {zone_id, zone_id.replace("zone:", "")}
    requested_ids.update({f"zone:{zid}" for zid in list(requested_ids) if zid})

    za = _svc.get("zone_automation")
    zone_engine = _svc.get("habitus_zones") or _svc.get("hub_zones")

    if zone_engine is not None:
        try:
            overview = zone_engine.get_overview()
            for zone in getattr(overview, "zones", []) or []:
                zid = zone.get("zone_id", "") if isinstance(zone, dict) else getattr(zone, "zone_id", "")
                if zid not in requested_ids:
                    continue

                full_zone = zone_engine.get_zone(zid)
                base_zone = dict(full_zone) if isinstance(full_zone, dict) else (dict(zone) if isinstance(zone, dict) else {"zone_id": zid})
                role_entities = {}
                if za and hasattr(za, "get_zone_entities_by_role"):
                    role_entities = za.get_zone_entities_by_role(zid) or {}

                merged_zone = dict(base_zone)
                merged_zone["zone_id"] = zid
                merged_zone["name_de"] = merged_zone.get("name_de") or merged_zone.get("name") or zid
                merged_zone["zone_type"] = str(merged_zone.get("zone_type", zid) or zid)
                merged_zone["enabled_modules"] = [
                    str(module_id) for module_id in merged_zone.get("enabled_modules", []) if str(module_id)
                ]
                merged_zone["entities_by_role"] = _merge_entities_by_role(role_entities, merged_zone.get("entities_by_role"))
                merged_zone["entity_ids"] = _normalize_entity_ids(merged_zone)
                if not merged_zone["entity_ids"]:
                    merged_zone["entity_ids"] = _normalize_entity_ids({"entities": merged_zone["entities_by_role"]})
                merged_zone["entities"] = merged_zone["entities_by_role"]
                return merged_zone
        except Exception:
            logger.debug("Failed to assemble zone aggregate from truth engine", exc_info=True)

    if za and hasattr(za, "get_all_states"):
        try:
            for s in za.get_all_states():
                zid = s.get("zone_id", "")
                if zid not in requested_ids:
                    continue
                entities = {}
                if hasattr(za, "get_zone_entities_by_role"):
                    entities = za.get_zone_entities_by_role(zid) or {}
                entities = _normalize_entities_by_role(entities)
                entity_ids = _normalize_entity_ids({"entities": entities})
                return {
                    "zone_id": zid,
                    "name_de": s.get("name", zid),
                    "zone_type": s.get("zone_type", zid),
                    "enabled_modules": [str(module_id) for module_id in s.get("enabled_modules", []) if str(module_id)],
                    "entity_ids": entity_ids,
                    "entities_by_role": entities,
                    "entities": entities,
                }
        except Exception:
            logger.debug("Failed to assemble zone aggregate from automation state", exc_info=True)

    # Fallback: habitus_zones + example_config
    try:
        from copilot_core.homeassistant.habitus_zones import get_all_zones
        zones = get_all_zones()
        try:
            from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES
        except ImportError:
            EXAMPLE_ZONE_ENTITIES = {}

        for z in zones:
            zid = z.get("zone_id", "") if isinstance(z, dict) else getattr(z, "zone_type", "")
            if hasattr(zid, "value"):
                zid = zid.value
            if zid in requested_ids:
                entities = _normalize_entities_by_role(EXAMPLE_ZONE_ENTITIES.get(zid, {}))
                return {
                    "zone_id": zid,
                    "name_de": z.get("name_de", zid) if isinstance(z, dict) else getattr(z, "name_de", zid),
                    "zone_type": z.get("zone_type", zid) if isinstance(z, dict) else zid,
                    "enabled_modules": [str(module_id) for module_id in (z.get("enabled_modules", []) if isinstance(z, dict) else []) if str(module_id)],
                    "entity_ids": _normalize_entity_ids({"entities": entities}),
                    "entities_by_role": entities,
                    "entities": entities,
                }
    except ImportError:
        pass
    return None


# ── Zone Presets ────────────────────────────────────────────────────────

ZONE_PRESETS = [
    {
        "preset_id": "morgen",
        "name_de": "Morgen",
        "icon": "mdi:weather-sunset-up",
        "description": "Sanftes Aufwachen: warmes Licht, moderate Temperatur",
        "actions": {
            "lights": {"brightness_pct": 60, "color_temp_k": 3500},
            "climate": {"target_temp": 21.0},
            "covers": {"position_pct": 100},
        },
    },
    {
        "preset_id": "tag",
        "name_de": "Tag",
        "icon": "mdi:white-balance-sunny",
        "description": "Volle Helligkeit, Rollos offen, Energie-Modus",
        "actions": {
            "lights": {"brightness_pct": 100, "color_temp_k": 5000},
            "climate": {"target_temp": 21.0},
            "covers": {"position_pct": 100},
        },
    },
    {
        "preset_id": "abend",
        "name_de": "Abend",
        "icon": "mdi:weather-sunset-down",
        "description": "Warmes Licht, gedimmt, Rollos zu",
        "actions": {
            "lights": {"brightness_pct": 40, "color_temp_k": 2700},
            "climate": {"target_temp": 20.5},
            "covers": {"position_pct": 0},
        },
    },
    {
        "preset_id": "nacht",
        "name_de": "Nacht",
        "icon": "mdi:weather-night",
        "description": "Alles aus, Heizung abgesenkt",
        "actions": {
            "lights": {"brightness_pct": 0},
            "climate": {"target_temp": 18.0},
            "covers": {"position_pct": 0},
        },
    },
    {
        "preset_id": "film",
        "name_de": "Film",
        "icon": "mdi:movie-open",
        "description": "Gedimmtes Licht, Rollos zu, Medien bereit",
        "actions": {
            "lights": {"brightness_pct": 10, "color_temp_k": 2500},
            "covers": {"position_pct": 0},
            "media": {"volume_pct": 60},
        },
    },
    {
        "preset_id": "party",
        "name_de": "Party",
        "icon": "mdi:party-popper",
        "description": "Volle Beleuchtung, Musik an",
        "actions": {
            "lights": {"brightness_pct": 100, "color_temp_k": 4000},
            "media": {"volume_pct": 70},
        },
    },
    {
        "preset_id": "konzentration",
        "name_de": "Konzentration",
        "icon": "mdi:head-lightbulb",
        "description": "Helles, kuehles Licht, keine Ablenkung",
        "actions": {
            "lights": {"brightness_pct": 90, "color_temp_k": 5000},
            "media": {"volume_pct": 0},
        },
    },
    {
        "preset_id": "abwesend",
        "name_de": "Abwesend",
        "icon": "mdi:home-export-outline",
        "description": "Energiesparmodus: alles aus, Heizung abgesenkt",
        "actions": {
            "lights": {"brightness_pct": 0},
            "climate": {"target_temp": 17.0},
            "covers": {"position_pct": 0},
            "media": {"volume_pct": 0},
        },
    },
    {
        "preset_id": "romantisch",
        "name_de": "Romantisch",
        "icon": "mdi:heart",
        "description": "Sanftes, warmes Licht, leise Musik",
        "actions": {
            "lights": {"brightness_pct": 20, "color_temp_k": 2200},
            "media": {"volume_pct": 25},
        },
    },
    {
        "preset_id": "gaeste",
        "name_de": "Gaeste",
        "icon": "mdi:account-group",
        "description": "Einladende Beleuchtung, angenehme Temperatur",
        "actions": {
            "lights": {"brightness_pct": 70, "color_temp_k": 3000},
            "climate": {"target_temp": 21.5},
        },
    },
]


# ── HA Scene Integration ────────────────────────────────────────────────

def _capture_zone_states(entity_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Capture current entity states from HA Supervisor API."""
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not ha_token:
        return {}

    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    capturable_domains = {
        "light", "switch", "cover", "climate", "fan",
        "media_player", "input_boolean", "input_number", "input_select",
    }

    domain_attrs = {
        "light": ["brightness", "color_temp_kelvin", "rgb_color", "hs_color", "color_mode"],
        "cover": ["current_position", "current_tilt_position"],
        "climate": ["temperature", "target_temp_high", "target_temp_low", "hvac_mode", "fan_mode", "preset_mode"],
        "fan": ["percentage", "preset_mode", "direction"],
        "media_player": ["volume_level", "is_volume_muted", "source", "media_content_type"],
    }

    entity_set = set(entity_ids)
    entity_states = {}
    try:
        resp = http_requests.get(
            f"{ha_url}/states", headers=headers, timeout=10,
        )
        if not resp.ok:
            logger.debug("Failed to fetch /states: %s", resp.status_code)
            return {}
        all_states = resp.json()
    except Exception:
        logger.debug("Failed to fetch /states for zone capture")
        return {}

    for state_data in all_states:
        eid = state_data.get("entity_id", "")
        if eid not in entity_set:
            continue
        domain = eid.split(".", 1)[0] if "." in eid else ""
        if domain not in capturable_domains:
            continue
        snapshot = {"state": state_data.get("state", "unknown")}
        attrs = state_data.get("attributes", {})
        for attr_key in domain_attrs.get(domain, []):
            val = attrs.get(attr_key)
            if val is not None:
                snapshot[attr_key] = val
        entity_states[eid] = snapshot

    return entity_states


def _create_ha_scene(scene_id: str, entity_ids: list[str]) -> str | None:
    """Register a scene in HA via snapshot and return scene entity_id."""
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not ha_token:
        return None
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    try:
        resp = http_requests.post(
            f"{ha_url}/services/scene/create",
            json={"scene_id": scene_id, "snapshot_entities": entity_ids},
            headers=headers, timeout=10,
        )
        if resp.ok:
            return f"scene.{scene_id}"
    except Exception:
        logger.debug("Failed to create HA scene %s", scene_id)
    return None


def _apply_ha_scene(ha_scene_eid: str) -> bool:
    """Apply a HA scene by entity_id."""
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not ha_token:
        return False
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    try:
        resp = http_requests.post(
            f"{ha_url}/services/scene/turn_on",
            json={"entity_id": ha_scene_eid},
            headers=headers, timeout=10,
        )
        return resp.ok
    except Exception:
        return False


# ── REST Endpoints ──────────────────────────────────────────────────────

@zone_aggregates_bp.route("/categories", methods=["GET"])
@require_token
def get_categories():
    """List all aggregate category definitions."""
    if _aggregator and hasattr(_aggregator, "get_category_defs"):
        cats = _aggregator.get_category_defs()
    else:
        from copilot_core.homeassistant.device_class_aggregator import AGGREGATE_CATEGORIES
        cats = [
            {
                "category_id": c.category_id,
                "name_de": c.name_de,
                "icon": c.icon,
                "domains": list(c.domains),
                "device_classes": list(c.device_classes),
                "unit": c.unit,
            }
            for c in AGGREGATE_CATEGORIES
        ]
    return jsonify({"ok": True, "categories": cats, "count": len(cats)})


@zone_aggregates_bp.route("/<zone_id>", methods=["GET"])
@require_token
def get_zone_aggregates(zone_id: str):
    """Get aggregated entities (Sammelentitaeten) for a zone."""
    zone = _get_zone(zone_id)
    if not zone:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' nicht gefunden"}), 404

    if _aggregator:
        results = _aggregator.aggregate_zone(zone["entity_ids"])
        aggregates = [r.to_dict() for r in results]
    else:
        aggregates = []

    return jsonify({
        "ok": True,
        "zone_id": zone["zone_id"],
        "zone_name": zone.get("name_de", zone_id),
        "zone_type": zone.get("zone_type", zone.get("zone_id", zone_id)),
        "enabled_modules": zone.get("enabled_modules", []),
        "entities_by_role": zone.get("entities_by_role", zone.get("entities", {})),
        "aggregates": aggregates,
        "total_entities": len(zone["entity_ids"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


@zone_aggregates_bp.route("/<zone_id>/presets", methods=["GET"])
@require_token
def get_zone_presets(zone_id: str):
    """Get zone-specific presets."""
    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "presets": ZONE_PRESETS,
        "count": len(ZONE_PRESETS),
    })


@zone_aggregates_bp.route("/<zone_id>/scenes", methods=["GET"])
@require_token
def get_zone_scenes(zone_id: str):
    """List saved scenes for a zone."""
    scenes = _load_zone_scenes(zone_id)
    # Strip entity_states for list view (can be large)
    for s in scenes:
        s["entity_count"] = len(s.get("entity_states", {}))
        s.pop("entity_states", None)
    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "scenes": scenes,
        "count": len(scenes),
    })


@zone_aggregates_bp.route("/<zone_id>/scene/capture", methods=["POST"])
@require_token
def capture_zone_scene(zone_id: str):
    """Capture current zone state as a scene (saved to SQLite + optionally HA scene).

    Body: {"name": "Gemuetlicher Abend", "create_ha_scene": true}
    """
    zone = _get_zone(zone_id)
    if not zone:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' nicht gefunden"}), 404

    body = request.get_json(silent=True) or {}
    scene_name = body.get("name") or f"{zone.get('name_de', zone_id)} — {time.strftime('%d.%m %H:%M')}"
    create_ha = body.get("create_ha_scene", True)

    entity_states = _capture_zone_states(zone["entity_ids"])
    if not entity_states:
        return jsonify({"ok": False, "error": "Keine steuerbaren Entitaeten gefunden oder HA nicht erreichbar"}), 400

    scene_id = f"hz_{zone_id.replace(':', '_')}_{uuid.uuid4().hex[:8]}"
    ha_scene_eid = None
    if create_ha:
        ha_scene_eid = _create_ha_scene(scene_id, list(entity_states.keys()))

    scene = {
        "scene_id": scene_id,
        "zone_id": zone_id,
        "zone_name": zone.get("name_de", zone_id),
        "name": scene_name,
        "entity_states": entity_states,
        "created_at": time.time(),
        "applied_count": 0,
        "last_applied": None,
        "source": "manual",
        "is_favorite": False,
        "ha_scene_entity_id": ha_scene_eid,
    }

    _save_scene(scene)

    # Publish bus event
    bus = _svc.get("bus")
    if bus:
        bus.publish("scene.captured", {
            "scene_id": scene_id,
            "zone_id": zone_id,
            "entity_count": len(entity_states),
        }, source="zone_aggregates")

    logger.info("Zone scene captured: %s (%s) for zone %s (%d entities)",
                scene_id, scene_name, zone_id, len(entity_states))

    scene_resp = dict(scene)
    scene_resp["entity_count"] = len(entity_states)
    scene_resp.pop("entity_states", None)  # Don't return full states in response

    return jsonify({"ok": True, "scene": scene_resp}), 201


@zone_aggregates_bp.route("/<zone_id>/scene/apply", methods=["POST"])
@require_token
def apply_zone_scene(zone_id: str):
    """Apply a saved scene to the zone.

    Body: {"scene_id": "hz_wohnbereich_abc12345"}
    """
    body = request.get_json(silent=True) or {}
    scene_id = body.get("scene_id")
    if not scene_id:
        return jsonify({"ok": False, "error": "scene_id ist erforderlich"}), 400

    scene = _load_scene(scene_id)
    if not scene:
        return jsonify({"ok": False, "error": f"Szene '{scene_id}' nicht gefunden"}), 404

    # Try HA scene first
    ha_eid = scene.get("ha_scene_entity_id")
    method = "manual"
    if ha_eid and _apply_ha_scene(ha_eid):
        method = "ha_scene"
    else:
        # Manual apply via individual service calls
        from copilot_core.api.v1.scenes import _apply_entity_state
        ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
        ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        for eid, state_data in scene.get("entity_states", {}).items():
            try:
                _apply_entity_state(ha_url, headers, eid, state_data)
            except Exception:
                logger.debug("Failed to apply state for %s", eid)

    _increment_apply_count(scene_id)

    # Publish bus event
    bus = _svc.get("bus")
    if bus:
        bus.publish("scene.applied", {
            "scene_id": scene_id,
            "zone_id": zone_id,
            "method": method,
        }, source="zone_aggregates")

    return jsonify({
        "ok": True,
        "scene_id": scene_id,
        "zone_id": zone_id,
        "method": method,
    })


@zone_aggregates_bp.route("/<zone_id>/scene/<scene_id>", methods=["DELETE"])
@require_token
def delete_zone_scene(zone_id: str, scene_id: str):
    """Delete a saved zone scene."""
    _delete_scene(scene_id)
    return jsonify({"ok": True, "deleted": scene_id})
