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
    GET  /api/v1/zone-automation/zones/<zone_id>/entities/read-model — Deterministic zone entity read-model
    POST /api/v1/zone-automation/zones/<zone_id>/entities   — Add entity to zone
    GET  /api/v1/zone-automation/entities/read-model         — Deterministic read-model for all assignments (?since=<revision>, deltas=true)
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
import re
from typing import Any, Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token, optional_token
from copilot_core.homeassistant.habitus_zones import ZoneType

_LOGGER = logging.getLogger(__name__)

zone_automation_bp = Blueprint(
    "zone_automation", __name__, url_prefix="/api/v1/zone-automation"
)

# Module-level service reference
_controller: Optional[Any] = None
_zone_engine: Optional[Any] = None




def _sanitize_zone_id(value: str) -> str:
    """Normalize a human zone name into a stable zone_id.
    Keeps lowercase a-z/0-9/underscores and hyphen fallback.
    """
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9\-_]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_-")
    if not raw:
        return "zone"
    return raw


def _normalize_zone_type(zone_type: str) -> str:
    """Normalize and validate zone_type values against ZoneType enum."""
    normalized = str(zone_type or "").strip().lower()
    return normalized if normalized in {item.value for item in ZoneType} else ""


def _mirror_zone_truth_into_habitus_engine(zone: dict[str, Any], cfg: Any) -> None:
    """Mirror synced HA zone definitions into the HabitusZone truth engine."""
    if _zone_engine is None:
        return

    try:
        _zone_engine.sync_external_zone_topology(
            str(zone.get("zone_id", "")).strip(),
            name=str(zone.get("name_de") or zone.get("name") or getattr(cfg, "zone_name", "") or zone.get("zone_id", "")).strip(),
            zone_type=_normalize_zone_type(str(zone.get("zone_type") or getattr(cfg, "zone_type", "living") or "living")) or "living",
            enabled_modules=set(getattr(cfg, "enabled_modules", set()) or set()),
            entities=list(zone.get("entities", getattr(cfg, "ha_entities", [])) or []),
            icon=str(zone.get("icon", "")).strip() or None,
            priority=zone.get("priority"),
            enabled=zone.get("enabled"),
        )
    except Exception as exc:
        _LOGGER.warning("Failed to mirror synced zone '%s' into Habitus engine: %s", zone.get("zone_id"), exc)


def init_zone_automation_api(controller=None, zone_engine=None) -> None:
    """Wire the zone automation controller and optional zone engine into the blueprint."""
    global _controller, _zone_engine
    _controller = controller
    _zone_engine = zone_engine
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


@zone_automation_bp.route("/zones", methods=["GET"])
@optional_token
def list_zones():
    """List all known zone automation configs."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    zones = list(_controller.get_all_configs().values())
    return jsonify({"ok": True, "zones": zones, "count": len(zones)})


@zone_automation_bp.route("/zones", methods=["POST"])
@require_token
def create_zone():
    """Create a Core-owned Habitus zone scaffold.

    Body:
        {
            "zone_id": "wohnzimmer",
            "zone_name": "Wohnzimmer",
            "zone_type": "living",
            "enabled_modules": ["light", "presence"],
            "habitus_sync": true
        }
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}
    zone_name = str(data.get("zone_name", "")).strip()
    zone_id = _sanitize_zone_id(data.get("zone_id") or zone_name)

    if not zone_id:
        return jsonify({"ok": False, "error": "zone_id is required"}), 400

    if zone_id in getattr(_controller, "_configs", {}):
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' already exists"}), 409

    cfg = _controller.get_zone_config(zone_id)

    updates: dict[str, Any] = {}
    if zone_name:
        updates["zone_name"] = zone_name

    zone_type = _normalize_zone_type(data.get("zone_type", ""))
    if data.get("zone_type") is not None and not zone_type:
        return jsonify({"ok": False, "error": f"Invalid zone_type: {data.get('zone_type')}"}), 400
    if zone_type:
        updates["zone_type"] = zone_type

    enabled_modules = data.get("enabled_modules")
    if isinstance(enabled_modules, list):
        updates["enabled_modules"] = [
            str(module_id).strip()
            for module_id in enabled_modules
            if str(module_id).strip()
        ]

    if updates:
        cfg = _controller.set_zone_config(zone_id, updates)

    if bool(data.get("habitus_sync", True)):
        try:
            zone_payload = {
                "zone_id": zone_id,
                "name_de": zone_name or zone_id,
                "name": zone_name or zone_id,
                "zone_type": getattr(cfg, "zone_type", "living") or "living",
                "area_id": zone_id,
                "entities": [],
            }
            _controller.sync_habitus_zones(zones=[zone_payload], clear_missing=False)
            _mirror_zone_truth_into_habitus_engine(zone_payload, cfg)
        except Exception:
            _LOGGER.debug("Core-owned zone scaffold sync failed for %s", zone_id, exc_info=True)

    return jsonify({"ok": True, "zone": cfg.to_dict()}), 201


@zone_automation_bp.route("/zones/<zone_id>", methods=["GET"])
@optional_token
def get_zone_state(zone_id: str):
    """Get zone automation state and config."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503
    return jsonify({"ok": True, **_controller.get_zone_state(zone_id)})


@zone_automation_bp.route("/zones/<zone_id>", methods=["DELETE"])
@require_token
def delete_zone(zone_id: str):
    """Delete a zone automation configuration and related runtime state."""
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    removed = _controller.delete_zone(zone_id)
    if not removed:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    if _zone_engine is not None:
        try:
            _zone_engine.delete_zone(zone_id)
        except Exception:
            _LOGGER.debug("Failed to remove zone '%s' from Habitus engine", zone_id)

    return jsonify({"ok": True, "zone_id": zone_id})


@zone_automation_bp.route("/zones/<zone_id>/config", methods=["POST"])
@require_token
def update_zone_config(zone_id: str):
    """Update zone automation config (partial updates).

    Body: {"light": {...}, "music": {...}, "zone_name": "..."}
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    data = request.get_json(silent=True) or {}

    if "zone_type" in data:
        normalized = _normalize_zone_type(data.get("zone_type"))
        if not normalized:
            return jsonify({"ok": False, "error": f"Invalid zone_type: {data.get('zone_type')}"}), 400
        data["zone_type"] = normalized

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


@zone_automation_bp.route("/zones/<zone_id>/entities/read-model", methods=["GET"])
@require_token
def get_zone_entities_read_model(zone_id: str):
    """Return a deterministic read-model for all assignments in one zone.

    Optional query param: ?since=<revision>
    If since is equal-or-latest revision, returns changed=False.
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    model = _controller.get_zone_entities_read_model(zone_id)
    current_revision = model["revision"]

    raw_since = request.args.get("since")
    if raw_since is not None:
        try:
            since = int(raw_since)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Invalid since parameter"}), 400
        if since < 0:
            return jsonify({"ok": False, "error": "since must be >= 0"}), 400

        if since >= current_revision:
            return jsonify({
                "ok": True,
                "changed": False,
                "zone_id": zone_id,
                "revision": current_revision,
            })

    return jsonify({"ok": True, "changed": True, **model})


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


@zone_automation_bp.route("/entities/read-model", methods=["GET"])
@require_token
def get_entities_read_model():
    """Return a deterministic read-model for all zone entity assignments.

    Query params:
      - since=<revision> (int, optional)
      - deltas=true (boolean, optional; **requires since**)
      - compact=true (boolean, optional)

    If since is equal-or-latest revision, returns changed=False with compact payload.
    With deltas=true and stale state, only zones changed since `since` are returned.
    With compact=true, entity objects are omitted from zone entries.
    """
    if _controller is None:
        return jsonify({"ok": False, "error": "Controller not initialized"}), 503

    raw_since = request.args.get("since")
    raw_deltas = request.args.get("deltas", "false").strip().lower()
    want_deltas = raw_deltas in {"1", "true", "yes", "on"}
    raw_compact = request.args.get("compact", "false").strip().lower()
    want_compact = raw_compact in {"1", "true", "yes", "on"}

    if want_deltas and raw_since is None:
        return jsonify({"ok": False, "error": "deltas=true requires since parameter"}), 400

    if raw_since is not None:
        try:
            since = int(raw_since)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Invalid since parameter"}), 400
        if since < 0:
            return jsonify({"ok": False, "error": "since must be >= 0"}), 400

        # If client cache is current, return compact unchanged payload.
        current_model = _controller.get_all_entities_read_model(compact=want_compact)
        current_revision = current_model["summary"]["revision"]
        if since >= current_revision:
            return jsonify({
                "ok": True,
                "changed": False,
                "revision": current_revision,
                "zones": [],
                "summary": current_model["summary"],
            })

        model = _controller.get_all_entities_read_model(
            since_revision=since,
            deltas=want_deltas,
            compact=want_compact,
        )

        if want_deltas and isinstance(model.get("summary", {}).get("returned_zone_count"), int):
            if model["summary"]["returned_zone_count"] == 0:
                return jsonify({
                    "ok": True,
                    "changed": False,
                    "revision": model["summary"]["delta_to_revision"],
                    "zones": [],
                    "summary": model["summary"],
                })
    else:
        model = _controller.get_all_entities_read_model(compact=want_compact)

    return jsonify({"ok": True, "changed": True, **model})


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


def _normalize_sync_zone_name(zone: dict[str, Any], zone_id: str) -> str:
    """Resolve the best display name from HA/Core contract variants."""
    for key in ("name", "name_de", "zone_name"):
        value = zone.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return zone_id



def _normalize_string_list(value: Any) -> list[str]:
    """Coerce list-like payload values into a de-duplicated string list."""
    if not isinstance(value, (list, tuple, set)):
        return []

    items: list[str] = []
    seen: set[str] = set()
    for raw in value:
        item = str(raw).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items



def _normalize_zone_entities(zone: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """Flatten HA zone payloads into entity_ids plus optional role hints.

    Accepts both:
    - entities: ["light.kitchen"]
    - entities: {"lights": ["light.kitchen"], "motion": ["binary_sensor.kitchen_motion"]}
    - entity_ids: ["light.kitchen", ...]
    """
    entity_ids: list[str] = []
    role_by_entity: dict[str, str] = {}
    seen: set[str] = set()

    def _add_entities(values: Any, *, role: str | None = None) -> None:
        for entity_id in _normalize_string_list(values):
            if entity_id not in seen:
                seen.add(entity_id)
                entity_ids.append(entity_id)
            if role and entity_id not in role_by_entity:
                role_by_entity[entity_id] = role

    entities_payload = zone.get("entities")
    if isinstance(entities_payload, dict):
        for raw_role, values in entities_payload.items():
            role = str(raw_role).strip() or None
            _add_entities(values, role=role)
    else:
        _add_entities(entities_payload)

    _add_entities(zone.get("entity_ids"))
    return entity_ids, role_by_entity


@zone_automation_bp.route("/sync-definitions", methods=["POST"])
@require_token
def sync_zone_definitions():
    """Receive full zone definitions from HA.

    HA pushes entity assignments, zone metadata, and HA context so Core's
    Brain/Neuron system has the full zone topology for categorization,
    habit learning, and suggestion generation.

    Body: {"source": "ha", "zones": [{"zone_id": "...", "name": "...",
                                       "entity_ids": [...], "entities": {...}}]}
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
            zone_name = _normalize_sync_zone_name(zone, zone_id)
            entity_ids, role_by_entity = _normalize_zone_entities(zone)
            ha_sync_source = f"{source}_sync"

            # Store HA entity definitions + zone metadata on the config
            cfg.zone_name = zone_name
            candidate_zone_type = _normalize_zone_type(str(zone.get("zone_type", "") or ""))
            cfg.zone_type = candidate_zone_type or getattr(cfg, "zone_type", "") or "room"

            if "enabled_modules" in zone and isinstance(zone.get("enabled_modules"), (list, tuple, set)):
                cfg.enabled_modules = {
                    str(mid).strip()
                    for mid in zone.get("enabled_modules", [])
                    if str(mid).strip()
                }

            cfg.ha_entities = list(entity_ids)
            cfg._ha_entities = {
                "entity_ids": entity_ids,
                "entities": zone.get("entities", {}),
                "role_by_entity": role_by_entity,
            }

            # Replace only HA-synced assignments for this zone, while preserving
            # manual/imported assignments created directly in Core.
            existing_assignments = _controller._entity_assignments.get(zone_id, [])
            _controller._entity_assignments[zone_id] = [
                assignment
                for assignment in existing_assignments
                if assignment.source != ha_sync_source
            ]

            # Move HA-synced entities out of other zones before re-adding them.
            incoming_entity_ids = set(entity_ids)
            if incoming_entity_ids:
                for other_zone_id, assignments in list(_controller._entity_assignments.items()):
                    if other_zone_id == zone_id:
                        continue
                    _controller._entity_assignments[other_zone_id] = [
                        assignment
                        for assignment in assignments
                        if not (
                            assignment.source == ha_sync_source
                            and assignment.entity_id in incoming_entity_ids
                        )
                    ]

            for entity_id in entity_ids:
                _controller.add_entity(
                    zone_id,
                    entity_id,
                    role=role_by_entity.get(entity_id),
                    source=ha_sync_source,
                )

            if hasattr(_controller, "sync_entities_from_topology"):
                _controller.sync_entities_from_topology(zone_id, list(entity_ids))

            _mirror_zone_truth_into_habitus_engine(zone, cfg)
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
