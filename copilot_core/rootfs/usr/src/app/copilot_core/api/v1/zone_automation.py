"""
Zone Automation API — Presence-based light & music control, entity management.

Blueprint prefix: /api/v1/zone-automation

Endpoints:
    GET  /api/v1/zone-automation/dashboard              — Full automation dashboard
    GET  /api/v1/zone-automation/zones/<zone_id>         — Zone state + config
    POST /api/v1/zone-automation/zones/<zone_id>/config   — Update zone config (light/music sliders)
    POST /api/v1/zone-automation/zones/<zone_id>/presence  — Report presence event
    POST /api/v1/zone-automation/zones/<zone_id>/brightness — Report brightness update
    POST /api/v1/zone-automation/zones/<zone_id>/override   — Toggle override switch
    POST /api/v1/zone-automation/zones/<zone_id>/mood       — Set mood state for zone
    GET  /api/v1/zone-automation/zones/<zone_id>/entities   — List zone entities
    POST /api/v1/zone-automation/zones/<zone_id>/entities   — Add entity to zone
    DELETE /api/v1/zone-automation/zones/<zone_id>/entities/<entity_id> — Remove entity
    POST /api/v1/zone-automation/zones/<zone_id>/entities/<entity_id>/tags — Update entity tags
    POST /api/v1/zone-automation/zones/<zone_id>/entities/<entity_id>/role — Update entity role
    GET  /api/v1/zone-automation/tags                    — List tag definitions
    GET  /api/v1/zone-automation/roles                   — List role definitions
    GET  /api/v1/zone-automation/entities/search         — Search entities
    GET  /api/v1/zone-automation/mood-profiles           — List all mood adjustment profiles
    POST /api/v1/zone-automation/import                  — Import from example config
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token, optional_token

_LOGGER = logging.getLogger(__name__)

zone_automation_bp = Blueprint(
    "zone_automation", __name__, url_prefix="/api/v1/zone-automation"
)

# Module-level service reference
_controller: Optional[Any] = None


def init_zone_automation_api(controller=None) -> None:
    """Wire the zone automation controller into the blueprint."""
    global _controller
    _controller = controller
    _LOGGER.info("Zone Automation API initialized")


# ── Dashboard ────────────────────────────────────────────────────────────────


@zone_automation_bp.route("/dashboard", methods=["GET"])
@optional_token
def get_dashboard():
    """Full automation dashboard with all zone states."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503
    return jsonify({"ok": True, **_controller.get_dashboard()})


# ── Zone config & state ──────────────────────────────────────────────────────


@zone_automation_bp.route("/zones/<zone_id>", methods=["GET"])
@optional_token
def get_zone_state(zone_id: str):
    """Get zone automation state and config."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503
    return jsonify({"ok": True, **_controller.get_zone_state(zone_id)})


@zone_automation_bp.route("/zones/<zone_id>/config", methods=["POST"])
@require_token
def update_zone_config(zone_id: str):
    """Update zone automation config (partial updates).

    Body: {"light": {...}, "music": {...}, "zone_name": "..."}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    config = _controller.set_zone_config(zone_id, data)
    return jsonify({"ok": True, "config": config.to_dict()})


@zone_automation_bp.route("/zones/<zone_id>/override", methods=["POST"])
@require_token
def toggle_override(zone_id: str):
    """Toggle light/music override switch.

    Body: {"light_enabled": true/false, "music_enabled": true/false}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    updates = {}
    if "light_enabled" in data:
        updates["light"] = {"enabled": bool(data["light_enabled"])}
    if "music_enabled" in data:
        updates["music"] = {"enabled": bool(data["music_enabled"])}

    config = _controller.set_zone_config(zone_id, updates)
    return jsonify({"ok": True, "config": config.to_dict()})


@zone_automation_bp.route("/zones/<zone_id>/mode", methods=["GET"])
@require_token
def get_automation_mode(zone_id: str):
    """Get automation mode for a zone."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503
    return jsonify({"ok": True, "zone_id": zone_id,
                    "automation_mode": _controller.get_automation_mode(zone_id)})


@zone_automation_bp.route("/zones/<zone_id>/mode", methods=["POST"])
@require_token
def set_automation_mode(zone_id: str):
    """Set automation mode for a zone.

    Body: {"mode": "off" | "learning" | "autonomy"}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "").strip().lower()
    if not mode:
        return jsonify({"ok": False, "error": "Missing 'mode'"}), 400

    success = _controller.set_automation_mode(zone_id, mode)
    if not success:
        return jsonify({"ok": False, "error": f"Invalid mode '{mode}'. Valid: off, learning, autonomy"}), 400

    return jsonify({"ok": True, "zone_id": zone_id, "automation_mode": mode})


# ── Presence & brightness events ─────────────────────────────────────────────


@zone_automation_bp.route("/zones/<zone_id>/presence", methods=["POST"])
@require_token
def report_presence(zone_id: str):
    """Report presence event.

    Body: {"detected": true/false}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    detected = data.get("detected", True)

    if detected:
        actions = _controller.on_presence_detected(zone_id)
    else:
        actions = _controller.on_presence_cleared(zone_id)

    return jsonify({"ok": True, "actions": actions})


@zone_automation_bp.route("/zones/<zone_id>/brightness", methods=["POST"])
@require_token
def report_brightness(zone_id: str):
    """Report brightness update for adaptive dimming.

    Body: {"indoor_lux": 150.0, "outdoor_lux": 5000.0}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    indoor = data.get("indoor_lux", 0.0)
    outdoor = data.get("outdoor_lux", 0.0)

    result = _controller.update_brightness(zone_id, indoor, outdoor)
    return jsonify({"ok": True, **result})


# ── Mood management ──────────────────────────────────────────────────────────


@zone_automation_bp.route("/zones/<zone_id>/mood", methods=["POST"])
@require_token
def set_zone_mood(zone_id: str):
    """Set the current mood state for a zone.

    Body: {"mood": "relax" | "focus" | "active" | "sleep" | "away" | "alert" | "social" | "recovery" | ...}

    The mood state adjusts light brightness and color temperature automatically
    when mood_aware_enabled is True in the zone's light config.
    Unknown mood states fall back to neutral defaults (factor=1.0, temp=4000K).
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    mood = data.get("mood", "").strip()
    if not mood:
        return jsonify({"ok": False, "error": "Missing 'mood' field"}), 400

    result = _controller.set_mood(zone_id, mood)
    return jsonify({"ok": True, **result})


@zone_automation_bp.route("/mood-profiles", methods=["GET"])
@optional_token
def get_mood_profiles():
    """List all available mood adjustment profiles.

    Returns the MOOD_ADJUSTMENTS dict mapping mood names to
    {brightness_factor, color_temp_k, transition_s}.
    """
    from copilot_core.hub.zone_automation import MOOD_ADJUSTMENTS
    return jsonify({"ok": True, "profiles": MOOD_ADJUSTMENTS})


# ── Entity management ────────────────────────────────────────────────────────


@zone_automation_bp.route("/zones/<zone_id>/entities", methods=["GET"])
@require_token
def list_zone_entities(zone_id: str):
    """List all entities in a zone, optionally grouped by role."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    by_role = request.args.get("by_role", "false").lower() == "true"
    if by_role:
        return jsonify({"ok": True, "zone_id": zone_id,
                        "entities_by_role": _controller.get_zone_entities_by_role(zone_id)})
    return jsonify({"ok": True, "zone_id": zone_id,
                    "entities": _controller.get_zone_entities(zone_id)})


@zone_automation_bp.route("/zones/<zone_id>/entities", methods=["POST"])
@require_token
def add_entity(zone_id: str):
    """Add entity to zone.

    Body: {"entity_id": "light.xyz", "role": "lights", "tags": ["licht"], "display_name": "..."}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    entity_id = data.get("entity_id", "").strip()
    if not entity_id:
        return jsonify({"ok": False, "error": "Missing entity_id"}), 400

    from dataclasses import asdict
    assignment = _controller.add_entity(
        zone_id=zone_id,
        entity_id=entity_id,
        role=data.get("role"),
        tags=data.get("tags"),
        display_name=data.get("display_name", ""),
    )
    return jsonify({"ok": True, "assignment": asdict(assignment)})


@zone_automation_bp.route("/zones/<zone_id>/entities/<path:entity_id>", methods=["DELETE"])
@require_token
def remove_entity(zone_id: str, entity_id: str):
    """Remove entity from zone."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    removed = _controller.remove_entity(zone_id, entity_id)
    if not removed:
        return jsonify({"ok": False, "error": "Entity not found in zone"}), 404
    return jsonify({"ok": True, "removed": entity_id})


@zone_automation_bp.route("/zones/<zone_id>/entities/<path:entity_id>/tags", methods=["POST"])
@require_token
def update_entity_tags(zone_id: str, entity_id: str):
    """Update tags for an entity.

    Body: {"tags": ["licht", "styx"]}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        return jsonify({"ok": False, "error": "tags must be a list"}), 400

    updated = _controller.update_entity_tags(zone_id, entity_id, tags)
    if not updated:
        return jsonify({"ok": False, "error": "Entity not found"}), 404
    return jsonify({"ok": True, "entity_id": entity_id, "tags": tags})


@zone_automation_bp.route("/zones/<zone_id>/entities/<path:entity_id>/role", methods=["POST"])
@require_token
def update_entity_role(zone_id: str, entity_id: str):
    """Update role for an entity.

    Body: {"role": "lights"}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    role = data.get("role", "").strip()
    if not role:
        return jsonify({"ok": False, "error": "Missing role"}), 400

    updated = _controller.update_entity_role(zone_id, entity_id, role)
    if not updated:
        return jsonify({"ok": False, "error": "Entity not found or invalid role"}), 404
    return jsonify({"ok": True, "entity_id": entity_id, "role": role})


# ── Tags & roles ─────────────────────────────────────────────────────────────


@zone_automation_bp.route("/tags", methods=["GET"])
@optional_token
def list_tags():
    """List all available tag definitions."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503
    return jsonify({"ok": True, "tags": _controller.get_tag_definitions()})


@zone_automation_bp.route("/roles", methods=["GET"])
@optional_token
def list_roles():
    """List all available entity roles."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503
    return jsonify({"ok": True, "roles": _controller.get_role_definitions()})


@zone_automation_bp.route("/entities/search", methods=["GET"])
@optional_token
def search_entities():
    """Search entities across all zones.

    Query param: ?q=search_term
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Missing query parameter 'q'"}), 400

    results = _controller.search_entities(query)
    return jsonify({"ok": True, "results": results, "count": len(results)})


# ── Import ───────────────────────────────────────────────────────────────────


@zone_automation_bp.route("/import", methods=["POST"])
@require_token
def import_entities():
    """Import entities from example config, custom data, or YAML.

    Body: {"source": "example"} or {"zones": {...}} or {"yaml": "zone_id: ..."}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}

    if data.get("source") == "example":
        from copilot_core.example_config import EXAMPLE_ZONE_ENTITIES
        count = _controller.import_from_example_config(EXAMPLE_ZONE_ENTITIES)
        return jsonify({"ok": True, "imported": count, "source": "example"})

    zones = data.get("zones")
    if zones and isinstance(zones, dict):
        count = _controller.import_from_example_config(zones)
        return jsonify({"ok": True, "imported": count, "source": "custom"})

    # YAML import support
    yaml_text = data.get("yaml") or data.get("yaml_text")
    if yaml_text and isinstance(yaml_text, str):
        try:
            import yaml as yaml_lib
            parsed = yaml_lib.safe_load_all(yaml_text)
            imported_count = 0
            for doc in parsed:
                if isinstance(doc, dict) and doc.get("zone_id"):
                    zone_entry = {doc["zone_id"]: doc}
                    try:
                        _controller.import_from_example_config(zone_entry)
                        imported_count += 1
                    except Exception:
                        pass
            return jsonify({"ok": True, "imported": imported_count, "source": "yaml"})
        except Exception as e:
            return jsonify({"ok": False, "error": f"YAML parse error: {e}"}), 400

    return jsonify({"ok": False, "error": "Provide 'source': 'example', 'zones' dict, or 'yaml' text"}), 400


# ── Ensure Zones ────────────────────────────────────────────────────────────


@zone_automation_bp.route("/ensure-zones", methods=["POST"])
@require_token
def ensure_zones():
    """Ensure zone automation configs exist for a list of zone IDs.

    Body: {
        "zone_ids": ["wohnbereich", "badbereich", ...],
        "habitus_sync": true   # optional: also register rooms+zones in HubZoneEngine
    }

    Auto-creates default ZoneAutomationConfig for each zone_id that
    doesn't exist yet.  When habitus_sync=true, also registers each
    zone_id as a room + zone in HabitusZoneEngine (hub_zones) so the
    zone_editor and habitus_zones APIs return them immediately.

    Returns the full dashboard afterwards.
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    zone_ids = data.get("zone_ids", [])
    if not isinstance(zone_ids, list):
        return jsonify({"ok": False, "error": "'zone_ids' must be a list"}), 400

    habitus_sync = bool(data.get("habitus_sync", False))
    created = []
    for zid in zone_ids:
        zid = str(zid).strip()
        if not zid:
            continue
        if zid not in _controller._configs:
            _controller.get_zone_config(zid)  # auto-creates default config
            created.append(zid)

        # ── HabitusZone sync ──────────────────────────────────────────
        if habitus_sync:
            try:
                _controller.sync_habitus_zones(zones=[{
                    "zone_id": zid,
                    "name": data.get("zone_names", {}).get(zid, zid),
                    "area_id": zid,
                    "entities": data.get("entities_by_zone", {}).get(zid, []),
                }])
            except Exception:
                _LOGGER.debug("habitus_sync failed for zone %s (non-fatal)", zid)

    _LOGGER.info("Ensured %d zone(s), created %d new: %s", len(zone_ids), len(created), created)
    return jsonify({"ok": True, "created": created, **_controller.get_dashboard()})



# ── HA ↔ Core Sync (HA calls this to push topology; gets back all Core state) ──


@zone_automation_bp.route("/sync", methods=["POST"])
@require_token
def sync_habitus_zones():
    """HA → Core zone topology sync + full Core state response.

    HA calls this after discovering areas and entities to:
    1. Register/update rooms and zones in HubZoneEngine (habitus_zones)
    2. Register/update zone configs in ZoneAutomationController

    Returns a complete snapshot of all Core zone state so HA can
    initialise its own entity↔zone mappings.

    Body: {
        "zones": [
            {
                "zone_id": "wohnbereich",
                "name": "Wohnbereich",
                "area_id": "wohnzimmer",
                "entities": ["light.wohnzimmer_decke", "sensor.wohnzimmer_temp"],
                "icon": "mdi:sofa",
                "priority": 10
            },
            ...
        ],
        "clear_missing": false   // if true, delete zones not in this payload
    }

    Response: {
        "ok": true,
        "synced": 5,
        "created": 2,
        "zone_automation_configs": [...],   // ZoneAutomationController state
        "habitus_zones": [...],            // HubZoneEngine overview
        "ha_should_update": {             // what HA should create/update locally
            "zones": [...],
            "entity_zone_map": {...}
        }
    }
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    zones = data.get("zones", [])
    clear_missing = bool(data.get("clear_missing", False))

    if not isinstance(zones, list):
        return jsonify({"ok": False, "error": "'zones' must be a list"}), 400

    try:
        result = _controller.sync_habitus_zones(zones=zones, clear_missing=clear_missing)
    except Exception as e:
        _LOGGER.exception("sync_habitus_zones failed")
        return jsonify({"ok": False, "error": f"sync failed: {e}"}), 500

    # Also include the current automation dashboard for HA to bootstrap from
    dashboard = _controller.get_dashboard()

    return jsonify({
        "ok": True,
        "synced": result.get("synced", 0),
        "created": result.get("created", 0),
        "deleted": result.get("deleted", 0),
        "zone_automation_configs": dashboard.get("zones", []),
        "habitus_zones": result.get("habitus_zones", []),
        "ha_should_update": {
            "zones": result.get("ha_zones", []),
            "entity_zone_map": result.get("entity_zone_map", {}),
        },
    })


# ── Sync Zone Definitions (HA → Core) ──────────────────────────────────────


@zone_automation_bp.route("/sync-definitions", methods=["POST"])
@require_token
def sync_zone_definitions():
    """Receive full zone definitions from HA.

    HA pushes entity assignments, zone metadata, and HA context so Core's
    Brain/Neuron system has the full zone topology for categorization,
    habit learning, and suggestion generation.

    Body: {"source": "ha", "zones": [{"zone_id": "...", "name_de": "...",
                                       "entities": [...], "zone_type": "..."}]}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    source = data.get("source", "ha")
    zones = data.get("zones", [])

    if not isinstance(zones, list):
        return jsonify({"ok": False, "error": "'zones' must be a list"}), 400

    synced = []
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        zone_id = str(zone.get("zone_id", "")).strip()
        if not zone_id:
            continue

        # Ensure zone config exists
        if zone_id not in _controller._configs:
            _controller.get_zone_config(zone_id)  # auto-creates default

        cfg = _controller._configs.get(zone_id)
        if cfg:
            # Store HA entity definitions + zone metadata on the config
            cfg.zone_name = zone.get("name_de", zone_id)
            cfg.zone_type = zone.get("zone_type", cfg.zone_type or "room")
            if "enabled_modules" in zone and isinstance(zone.get("enabled_modules"), list):
                cfg.enabled_modules = set(str(mid) for mid in zone.get("enabled_modules", []) if str(mid).strip())
            if "entities" in zone:
                cfg.ha_entities = list(zone["entities"])
                cfg._ha_entities = list(zone["entities"])  # backward-compatible HA context for Brain
            synced.append(zone_id)

    _LOGGER.info(
        "[sync-definitions] Received %d zone definitions from %s, synced: %s",
        len(zones), source, synced,
    )
    return jsonify({"ok": True, "synced": synced, "count": len(synced)})


# ── Module Schemas ──────────────────────────────────────────────────────────


@zone_automation_bp.route("/module-schemas", methods=["GET"])
@optional_token
def get_module_schemas():
    """Self-describing schemas for all registered zone modules.

    Returns module_id -> {name_de, icon, color, fields: [...]} for each
    registered module. HA uses this to dynamically create entities.
    """
    from copilot_core.hub.zone_modules import ZoneModuleRegistry
    return jsonify({"ok": True, "schemas": ZoneModuleRegistry.get_all_schemas()})


@zone_automation_bp.route("/zones/<zone_id>/modules/<module_id>", methods=["GET"])
@optional_token
def get_zone_module_config(zone_id: str, module_id: str):
    """Get module config for a specific zone."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    config = _controller.get_zone_config(zone_id)
    mod = config.modules.get(module_id)
    if mod is None:
        return jsonify({"ok": False, "error": f"Unknown module '{module_id}'"}), 404

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "module_id": module_id,
        "config": mod.to_dict(),
    })


@zone_automation_bp.route("/zones/<zone_id>/modules/<module_id>", methods=["POST"])
@require_token
def set_zone_module_config(zone_id: str, module_id: str):
    """Update module config for a specific zone.

    Body: {"brightness_target_pct": 70, "enabled": true, ...}
    Accepts any field keys defined in the module's field_specs.
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    config = _controller.set_zone_config(zone_id, {"modules": {module_id: data}})
    mod = config.modules.get(module_id)
    if mod is None:
        return jsonify({"ok": False, "error": f"Unknown module '{module_id}'"}), 404

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "module_id": module_id,
        "config": mod.to_dict(),
    })


@zone_automation_bp.route("/zones/<zone_id>/modules/<module_id>/entities", methods=["GET"])
@optional_token
def get_zone_module_entities(zone_id: str, module_id: str):
    """Get entities matching this module (via tag/role/domain matching)."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    from copilot_core.hub.zone_modules import ZoneModuleRegistry
    mod_cls = ZoneModuleRegistry.get(module_id)
    if mod_cls is None:
        return jsonify({"ok": False, "error": f"Unknown module '{module_id}'"}), 404

    all_entities = _controller.get_zone_entities(zone_id)
    matching = [
        e for e in all_entities
        if mod_cls.matches_entity(e["entity_id"], e.get("role", ""), e.get("tags", []))
    ]

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "module_id": module_id,
        "entities": matching,
        "count": len(matching),
    })
