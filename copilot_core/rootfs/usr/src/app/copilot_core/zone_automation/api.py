"""Zone Automation REST API -- Flask blueprint for zone automation control.

Blueprint prefix: /api/v1/zone-automation

Endpoints:
    GET  /status                    -- All zones status
    GET  /status/<zone_id>          -- Single zone status
    POST /config/<zone_id>          -- Upsert zone automation config
    GET  /config                    -- All configs
    GET  /config/<zone_id>          -- Single config
    DELETE /config/<zone_id>        -- Delete config
    POST /evaluate                  -- Evaluate all zones
    POST /evaluate/<zone_id>        -- Evaluate single zone
    POST /sensor-update             -- Receive sensor update from HA
    POST /sync-zones                -- Sync from habitus zones (auto-tag entities)

All endpoints require a valid auth token (Bearer or X-Auth-Token).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

zone_automation_bp = Blueprint(
    "zone_automation", __name__, url_prefix="/api/v1/zone-automation"
)

# Module-level controller reference (set via init_zone_automation_api)
_controller = None


def init_zone_automation_api(controller) -> None:
    """Wire the ZoneAutomationController into the blueprint.

    Called from core_setup.register_blueprints().

    Parameters
    ----------
    controller : ZoneAutomationController
        The initialized controller instance.
    """
    global _controller
    _controller = controller
    _LOGGER.info("Zone Automation API initialized")


def _get_controller():
    """Get the zone automation controller, or None if not initialized."""
    return _controller


def _service_unavailable():
    """Return a 503 JSON response when the controller is not ready."""
    return jsonify({
        "ok": False,
        "error": "Zone automation controller not initialized",
    }), 503


# ---- Status Endpoints ------------------------------------------------------


@zone_automation_bp.route("/status", methods=["GET"])
@require_token
def get_all_status():
    """Get current status for all zones.

    Response::

        {
            "ok": true,
            "zones": [...],
            "count": 3
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    statuses = ctrl.get_all_status()
    return jsonify({
        "ok": True,
        "zones": statuses,
        "count": len(statuses),
    })


@zone_automation_bp.route("/status/<path:zone_id>", methods=["GET"])
@require_token
def get_zone_status(zone_id: str):
    """Get current status for a single zone.

    Response::

        {
            "ok": true,
            "zone": { ... }
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    status = ctrl.get_zone_status(zone_id)
    if status is None:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    return jsonify({"ok": True, "zone": status})


# ---- Config Endpoints -------------------------------------------------------


@zone_automation_bp.route("/config", methods=["GET"])
@require_token
def get_all_configs():
    """Get all zone automation configs.

    Response::

        {
            "ok": true,
            "configs": [...],
            "count": 3
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    configs = ctrl.get_all_configs()
    return jsonify({
        "ok": True,
        "configs": configs,
        "count": len(configs),
    })


@zone_automation_bp.route("/config/<path:zone_id>", methods=["GET"])
@require_token
def get_zone_config(zone_id: str):
    """Get a single zone automation config.

    Response::

        {
            "ok": true,
            "config": { ... }
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    config = ctrl.get_zone_config(zone_id)
    if config is None:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    return jsonify({"ok": True, "config": config})


@zone_automation_bp.route("/config/<path:zone_id>", methods=["POST"])
@require_token
def upsert_zone_config(zone_id: str):
    """Create or update a zone automation config.

    Request body: ZoneAutomationConfig fields (partial update supported)::

        {
            "enabled": true,
            "presence_sensors": ["binary_sensor.kitchen_motion"],
            "presence_timeout_s": 300,
            "presence_mode": "bayesian",
            "light_entities": ["light.kitchen_ceiling"],
            "light_mode": "auto",
            "min_brightness_pct": 10,
            "max_brightness_pct": 100,
            "color_temp_min_k": 2200,
            "color_temp_max_k": 5500,
            "indoor_brightness_sensors": ["sensor.kitchen_lux"],
            "outdoor_brightness_sensor": "sensor.outdoor_lux",
            "target_lux": 400.0,
            "media_players": ["media_player.kitchen_sonos"],
            "media_follow_presence": true
        }

    Response::

        {
            "ok": true,
            "config": { ... }
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    data = request.get_json(silent=True) or {}
    config = ctrl.update_zone_config(zone_id, data)
    return jsonify({"ok": True, "config": config})


@zone_automation_bp.route("/config/<path:zone_id>", methods=["DELETE"])
@require_token
def delete_zone_config(zone_id: str):
    """Delete a zone automation config.

    Response::

        {"ok": true, "deleted": "zone:kitchen"}
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    existed = ctrl.delete_zone_config(zone_id)
    if not existed:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    return jsonify({"ok": True, "deleted": zone_id})


# ---- Evaluate Endpoints -----------------------------------------------------


@zone_automation_bp.route("/evaluate", methods=["POST"])
@require_token
def evaluate_all():
    """Evaluate all zones and return automation recommendations.

    Response::

        {
            "ok": true,
            "evaluations": [
                {
                    "zone_id": "zone:kitchen",
                    "presence_state": "occupied",
                    "presence_confidence": 0.87,
                    "light_action": "turn_on",
                    "light_brightness_pct": 75,
                    "light_color_temp_k": 4200,
                    "light_reason": "presence_with_brightness",
                    ...
                },
                ...
            ],
            "count": 3
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    evaluations = ctrl.evaluate_all_zones()
    results = [e.to_dict() for e in evaluations]
    return jsonify({
        "ok": True,
        "evaluations": results,
        "count": len(results),
    })


@zone_automation_bp.route("/evaluate/<path:zone_id>", methods=["POST"])
@require_token
def evaluate_zone(zone_id: str):
    """Evaluate a single zone and return automation recommendations.

    Response::

        {
            "ok": true,
            "evaluation": { ... }
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    evaluation = ctrl.evaluate_zone(zone_id)
    return jsonify({
        "ok": True,
        "evaluation": evaluation.to_dict(),
    })


# ---- Sensor Update Endpoint -------------------------------------------------


@zone_automation_bp.route("/sensor-update", methods=["POST"])
@require_token
def sensor_update():
    """Receive a sensor state update from HA.

    This is the primary ingestion endpoint.  The HA integration calls this
    whenever a tracked sensor changes state.

    Request body::

        {
            "entity_id": "binary_sensor.kitchen_motion",
            "new_state": "on",
            "attributes": {
                "device_class": "motion",
                "friendly_name": "Kitchen Motion"
            }
        }

    Response::

        {
            "ok": true,
            "affected_zones": [...],
            "evaluations": [...]
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    data = request.get_json(silent=True) or {}
    entity_id = data.get("entity_id", "")
    new_state = str(data.get("new_state", ""))
    attributes = data.get("attributes", {})

    if not entity_id:
        return jsonify({"ok": False, "error": "Missing entity_id"}), 400

    evaluations = ctrl.process_sensor_update(entity_id, new_state, attributes)

    affected_zones = [e.get("zone_id", "") for e in evaluations]
    return jsonify({
        "ok": True,
        "entity_id": entity_id,
        "new_state": new_state,
        "affected_zones": affected_zones,
        "evaluations": evaluations,
    })


# ---- Sync Endpoint -----------------------------------------------------------


@zone_automation_bp.route("/sync-zones", methods=["POST"])
@require_token
def sync_zones():
    """Sync zone automation configs from habitus zone definitions.

    Auto-tags entities by domain to populate presence_sensors, light_entities,
    brightness_sensors, and media_players.

    Request body::

        {
            "zones": [
                {
                    "zone_id": "zone:kitchen",
                    "name": "Kitchen",
                    "entities": [
                        "binary_sensor.kitchen_motion",
                        "light.kitchen_ceiling",
                        "sensor.kitchen_lux",
                        "media_player.kitchen_sonos"
                    ]
                },
                ...
            ]
        }

    Response::

        {
            "ok": true,
            "created": 2,
            "updated": 1,
            "skipped": 0,
            "total_zones": 3
        }
    """
    ctrl = _get_controller()
    if ctrl is None:
        return _service_unavailable()

    data = request.get_json(silent=True) or {}
    zones = data.get("zones", [])

    if not isinstance(zones, list):
        return jsonify({"ok": False, "error": "zones must be a list"}), 400

    result = ctrl.sync_from_habitus_zones(zones)
    return jsonify({"ok": True, **result})
