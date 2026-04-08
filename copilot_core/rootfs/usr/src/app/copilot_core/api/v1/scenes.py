"""Scene REST API — Habitus zone scene management.

Provides endpoints for creating, listing, applying, and deleting zone scenes.
Integrates with HA Supervisor API for scene creation and activation.
"""

from flask import Blueprint, request, jsonify
import logging
import os
import time
import uuid

import requests as http_requests

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

scenes_bp = Blueprint("scenes", __name__, url_prefix="/api/v1/scenes")

# In-memory scene cache (synced from HACS integration via /update endpoint)
_scene_cache: dict[str, dict] = {}


@scenes_bp.route("", methods=["GET"])
@require_token
def list_scenes():
    """List all saved zone scenes."""
    zone_id = request.args.get("zone_id")
    scenes = list(_scene_cache.values())
    if zone_id:
        scenes = [s for s in scenes if s.get("zone_id") == zone_id]
    return jsonify({
        "scenes": scenes,
        "count": len(scenes),
    })


@scenes_bp.route("/presets", methods=["GET"])
@require_token
def list_presets():
    """List built-in scene presets."""
    presets = [
        {
            "preset_id": "morgen",
            "name": "Morgen",
            "icon": "mdi:weather-sunset-up",
            "description": "Sanfte Beleuchtung, angenehme Temperatur zum Aufwachen",
        },
        {
            "preset_id": "tag",
            "name": "Tag",
            "icon": "mdi:white-balance-sunny",
            "description": "Volle Helligkeit, Rollos offen, normale Temperatur",
        },
        {
            "preset_id": "abend",
            "name": "Abend",
            "icon": "mdi:weather-sunset-down",
            "description": "Warmes Licht, gedimmt, Rollos geschlossen",
        },
        {
            "preset_id": "nacht",
            "name": "Nacht",
            "icon": "mdi:weather-night",
            "description": "Alles aus, Rollos zu, Heizung heruntergefahren",
        },
        {
            "preset_id": "film",
            "name": "Film",
            "icon": "mdi:movie-open",
            "description": "Gedimmtes Licht, Rollos zu, Medien bereit",
        },
        {
            "preset_id": "party",
            "name": "Party",
            "icon": "mdi:party-popper",
            "description": "Bunte Beleuchtung, volle Helligkeit",
        },
        {
            "preset_id": "konzentration",
            "name": "Konzentration",
            "icon": "mdi:head-lightbulb",
            "description": "Helles, kuehles Licht fuer konzentriertes Arbeiten",
        },
        {
            "preset_id": "abwesend",
            "name": "Abwesend",
            "icon": "mdi:home-export-outline",
            "description": "Energiesparmodus: alles aus, Heizung abgesenkt",
        },
    ]
    return jsonify({"presets": presets})


@scenes_bp.route("/create", methods=["POST"])
@require_token
def create_scene():
    """Create a scene from current zone entity states.

    Body: {
        "zone_id": "zone:wohnzimmer",
        "zone_name": "Wohnzimmer",
        "name": "Gemütlicher Abend",  // optional
        "entity_ids": ["light.wohnzimmer", "cover.wohnzimmer", ...]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    zone_id = data.get("zone_id", "")
    zone_name = data.get("zone_name", zone_id)
    scene_name = data.get("name")
    entity_ids = data.get("entity_ids", [])

    if not zone_id:
        return jsonify({"error": "zone_id is required"}), 400
    if not entity_ids:
        return jsonify({"error": "entity_ids list is required"}), 400

    # Fetch current entity states from HA
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not ha_token:
        return jsonify({"error": "No SUPERVISOR_TOKEN"}), 503

    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}

    entity_states = {}
    capturable_domains = {"light", "switch", "cover", "climate", "fan", "media_player",
                          "input_boolean", "input_number", "input_select"}

    for eid in entity_ids:
        domain = eid.split(".", 1)[0] if "." in eid else ""
        if domain not in capturable_domains:
            continue
        try:
            resp = http_requests.get(f"{ha_url}/states/{eid}", headers=headers, timeout=5)
            if resp.ok:
                state_data = resp.json()
                snapshot = {"state": state_data.get("state", "unknown")}
                attrs = state_data.get("attributes", {})

                # Capture relevant attributes per domain
                domain_attrs = {
                    "light": ["brightness", "color_temp_kelvin", "rgb_color", "hs_color"],
                    "cover": ["current_position", "current_tilt_position"],
                    "climate": ["temperature", "target_temp_high", "target_temp_low", "hvac_mode"],
                    "fan": ["percentage", "preset_mode"],
                    "media_player": ["volume_level", "is_volume_muted", "source"],
                }
                for attr_key in domain_attrs.get(domain, []):
                    val = attrs.get(attr_key)
                    if val is not None:
                        snapshot[attr_key] = val

                entity_states[eid] = snapshot
        except Exception as exc:
            logger.warning("Failed to fetch state for %s: %s", eid, exc)

    if not entity_states:
        return jsonify({"error": "Keine steuerbaren Entitaeten gefunden"}), 400

    # Create scene
    scene_id = f"zone_scene_{uuid.uuid4().hex[:12]}"
    name = scene_name or f"{zone_name} — {time.strftime('%d.%m %H:%M')}"

    scene = {
        "scene_id": scene_id,
        "zone_id": zone_id,
        "zone_name": zone_name,
        "name": name,
        "entity_states": entity_states,
        "created_at": time.time(),
        "applied_count": 0,
        "last_applied": None,
        "source": "manual",
        "is_favorite": False,
        "ha_scene_entity_id": None,
    }

    # Register HA scene via snapshot
    try:
        resp = http_requests.post(
            f"{ha_url}/services/scene/create",
            json={
                "scene_id": scene_id,
                "snapshot_entities": list(entity_states.keys()),
            },
            headers=headers, timeout=10,
        )
        if resp.ok:
            scene["ha_scene_entity_id"] = f"scene.{scene_id}"
            logger.info("HA scene created: scene.%s", scene_id)
    except Exception as exc:
        logger.warning("Failed to create HA scene: %s", exc)

    _scene_cache[scene_id] = scene
    logger.info("Scene created: %s (%s) for zone %s", scene_id, name, zone_id)

    return jsonify({"success": True, "scene": scene}), 201


@scenes_bp.route("/<scene_id>/apply", methods=["POST"])
@require_token
def apply_scene(scene_id):
    """Apply a saved scene — restore entity states."""
    scene = _scene_cache.get(scene_id)
    if not scene:
        return jsonify({"error": f"Szene '{scene_id}' nicht gefunden"}), 404

    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not ha_token:
        return jsonify({"error": "No SUPERVISOR_TOKEN"}), 503

    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}

    # Try HA scene.turn_on first (if registered)
    ha_scene_eid = scene.get("ha_scene_entity_id")
    if ha_scene_eid:
        try:
            resp = http_requests.post(
                f"{ha_url}/services/scene/turn_on",
                json={"entity_id": ha_scene_eid},
                headers=headers, timeout=10,
            )
            if resp.ok:
                scene["applied_count"] = scene.get("applied_count", 0) + 1
                scene["last_applied"] = time.time()
                return jsonify({"success": True, "method": "ha_scene", "scene": scene})
        except Exception:
            logger.debug("HA scene turn_on failed, falling back to manual apply")

    # Manual apply: set each entity's state
    errors = []
    for eid, state_data in scene.get("entity_states", {}).items():
        try:
            _apply_entity_state(ha_url, headers, eid, state_data)
        except Exception as exc:
            errors.append(f"{eid}: {exc}")

    scene["applied_count"] = scene.get("applied_count", 0) + 1
    scene["last_applied"] = time.time()

    if errors:
        return jsonify({"success": True, "warnings": errors, "scene": scene})
    return jsonify({"success": True, "scene": scene})


@scenes_bp.route("/<scene_id>", methods=["DELETE"])
@require_token
def delete_scene(scene_id):
    """Delete a saved scene."""
    if scene_id not in _scene_cache:
        return jsonify({"error": f"Szene '{scene_id}' nicht gefunden"}), 404
    del _scene_cache[scene_id]
    return jsonify({"success": True, "deleted": scene_id})


@scenes_bp.route("/update", methods=["POST"])
@require_token
def update_scene_cache():
    """Receive scene data from HACS integration (sync)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400
    scenes = data.get("scenes", [])
    for s in scenes:
        sid = s.get("scene_id")
        if sid:
            _scene_cache[sid] = s
    return jsonify({"success": True, "synced": len(scenes)})


def _apply_entity_state(ha_url: str, headers: dict, entity_id: str, state_data: dict):
    """Apply a specific state to an entity via HA Supervisor API."""
    domain = entity_id.split(".", 1)[0]
    target_state = state_data.get("state", "")

    if domain == "light":
        if target_state == "off":
            http_requests.post(
                f"{ha_url}/services/light/turn_off",
                json={"entity_id": entity_id}, headers=headers, timeout=5
            )
        else:
            sdata = {"entity_id": entity_id}
            for k in ("brightness", "color_temp_kelvin", "rgb_color"):
                if k in state_data:
                    sdata[k] = state_data[k]
            http_requests.post(
                f"{ha_url}/services/light/turn_on",
                json=sdata, headers=headers, timeout=5
            )

    elif domain in ("switch", "input_boolean"):
        service = "turn_on" if target_state == "on" else "turn_off"
        http_requests.post(
            f"{ha_url}/services/{domain}/{service}",
            json={"entity_id": entity_id}, headers=headers, timeout=5
        )

    elif domain == "cover":
        pos = state_data.get("current_position")
        if pos is not None:
            http_requests.post(
                f"{ha_url}/services/cover/set_cover_position",
                json={"entity_id": entity_id, "position": pos},
                headers=headers, timeout=5
            )

    elif domain == "climate":
        sdata = {"entity_id": entity_id}
        if "hvac_mode" in state_data:
            sdata["hvac_mode"] = state_data["hvac_mode"]
        if "temperature" in state_data:
            sdata["temperature"] = state_data["temperature"]
        if "hvac_mode" in sdata:
            http_requests.post(
                f"{ha_url}/services/climate/set_hvac_mode",
                json=sdata, headers=headers, timeout=5
            )
        elif "temperature" in sdata:
            http_requests.post(
                f"{ha_url}/services/climate/set_temperature",
                json=sdata, headers=headers, timeout=5
            )

    elif domain == "fan":
        if target_state == "off":
            http_requests.post(
                f"{ha_url}/services/fan/turn_off",
                json={"entity_id": entity_id}, headers=headers, timeout=5
            )
        else:
            sdata = {"entity_id": entity_id}
            if "percentage" in state_data:
                sdata["percentage"] = state_data["percentage"]
            http_requests.post(
                f"{ha_url}/services/fan/turn_on",
                json=sdata, headers=headers, timeout=5
            )

    elif domain == "media_player":
        if target_state in ("off", "idle", "standby"):
            http_requests.post(
                f"{ha_url}/services/media_player/turn_off",
                json={"entity_id": entity_id}, headers=headers, timeout=5
            )


def get_scene_context_for_llm() -> str:
    """Build scene context string for LLM system prompt injection."""
    if not _scene_cache:
        return ""
    zone_scenes: dict[str, list[str]] = {}
    for s in _scene_cache.values():
        zname = s.get("zone_name", s.get("zone_id", "?"))
        zone_scenes.setdefault(zname, []).append(s.get("name", "?"))
    lines = [f"Gespeicherte Szenen ({len(_scene_cache)} total):"]
    for zname, names in zone_scenes.items():
        sample = names[:4]
        suffix = f" (+{len(names)-4})" if len(names) > 4 else ""
        lines.append(f"  {zname}: {', '.join(sample)}{suffix}")
    return "\n".join(lines) if len(lines) > 1 else ""
