"""Adaptive Light Module REST API — Zone-based adaptive lighting control.

Blueprint prefix: /api/v1/light-module

Endpoints:
    GET  /api/v1/light-module/zones              — List all zone light profiles
    GET  /api/v1/light-module/zones/<zone_id>     — Get a single zone profile
    POST /api/v1/light-module/zones/<zone_id>     — Create/update zone light profile
    DELETE /api/v1/light-module/zones/<zone_id>   — Delete zone light profile
    GET  /api/v1/light-module/status              — Current light state per zone
    GET  /api/v1/light-module/status/<zone_id>    — Current light state for one zone
    POST /api/v1/light-module/evaluate            — Evaluate and compute light settings
    POST /api/v1/light-module/evaluate/<zone_id>  — Evaluate a single zone
    GET  /api/v1/light-module/config              — Get global light module config
    POST /api/v1/light-module/config              — Update global light module config
    POST /api/v1/light-module/presence/<zone_id>  — Update presence for a zone
    POST /api/v1/light-module/brightness/<zone_id> — Update brightness readings
    POST /api/v1/light-module/apply/<zone_id>     — Apply computed settings to HA lights

All endpoints require a valid auth token (Bearer or X-Auth-Token).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests as http_requests
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token

_LOGGER = logging.getLogger(__name__)

light_module_bp = Blueprint(
    "light_module", __name__, url_prefix="/api/v1/light-module"
)

# Module-level service reference (set via init_light_module_api)
_service = None


def init_light_module_api(service) -> None:
    """Wire the LightModuleService into the blueprint.

    Called from core_setup.register_blueprints().
    """
    global _service
    _service = service
    _LOGGER.info("Light Module API initialized")


def _get_service():
    """Get the light module service, returning error response if not available."""
    if _service is None:
        return None
    return _service


# ---- Zone Profile Endpoints -----------------------------------------------


@light_module_bp.route("/zones", methods=["GET"])
@require_token
def list_zones():
    """List all zone light profiles.

    Response::

        {
            "ok": true,
            "zones": [...],
            "count": 3
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    profiles = svc.get_zone_profiles()
    return jsonify({
        "ok": True,
        "zones": profiles,
        "count": len(profiles),
    })


@light_module_bp.route("/zones/<path:zone_id>", methods=["GET"])
@require_token
def get_zone(zone_id: str):
    """Get a single zone light profile.

    Response::

        {
            "ok": true,
            "zone": { ... }
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    profile = svc.get_zone_profile(zone_id)
    if profile is None:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    return jsonify({"ok": True, "zone": profile})


@light_module_bp.route("/zones/<path:zone_id>", methods=["POST"])
@require_token
def upsert_zone(zone_id: str):
    """Create or update a zone light profile.

    Request body: ZoneLightProfile fields (partial update supported)::

        {
            "enabled": true,
            "lights": ["light.wohnzimmer_decke", "light.wohnzimmer_stehlampe"],
            "motion_sensor": "binary_sensor.wohnzimmer_motion",
            "brightness_sensor": "sensor.wohnzimmer_helligkeit",
            "outdoor_brightness_sensor": "sensor.outdoor_lux",
            "min_brightness_pct": 10,
            "max_brightness_pct": 100,
            "color_temp_min_k": 2200,
            "color_temp_max_k": 5500,
            "presence_timeout_s": 300,
            "mode": "auto"
        }

    Response::

        {
            "ok": true,
            "zone": { ... }
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    data = request.get_json(silent=True) or {}
    profile = svc.upsert_zone_profile(zone_id, data)
    return jsonify({"ok": True, "zone": profile})


@light_module_bp.route("/zones/<path:zone_id>", methods=["DELETE"])
@require_token
def delete_zone(zone_id: str):
    """Delete a zone light profile.

    Response::

        {"ok": true, "deleted": "zone:wohnbereich"}
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    existed = svc.delete_zone_profile(zone_id)
    if not existed:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    return jsonify({"ok": True, "deleted": zone_id})


# ---- Status Endpoints ------------------------------------------------------


@light_module_bp.route("/status", methods=["GET"])
@require_token
def get_status():
    """Get current light state for all zones.

    Response::

        {
            "ok": true,
            "zones": [...],
            "count": 3
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    statuses = svc.get_all_status()
    return jsonify({
        "ok": True,
        "zones": statuses,
        "count": len(statuses),
    })


@light_module_bp.route("/status/<path:zone_id>", methods=["GET"])
@require_token
def get_zone_status(zone_id: str):
    """Get current light state for a single zone.

    Response::

        {
            "ok": true,
            "zone": { ... }
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    status = svc.get_zone_status(zone_id)
    if status is None:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    return jsonify({"ok": True, "zone": status})


# ---- Evaluate Endpoints ----------------------------------------------------


@light_module_bp.route("/evaluate", methods=["POST"])
@require_token
def evaluate_all():
    """Evaluate and compute light settings for all zones.

    Response::

        {
            "ok": true,
            "evaluations": [
                {
                    "zone_id": "zone:wohnbereich",
                    "brightness_pct": 75,
                    "color_temp_k": 4200,
                    "should_be_on": true,
                    "reason": "brightness_ratio"
                },
                ...
            ]
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    results = svc.evaluate_all()
    return jsonify({
        "ok": True,
        "evaluations": results,
    })


@light_module_bp.route("/evaluate/<path:zone_id>", methods=["POST"])
@require_token
def evaluate_zone(zone_id: str):
    """Evaluate and compute light settings for a single zone.

    Response::

        {
            "ok": true,
            "zone_id": "zone:wohnbereich",
            "brightness_pct": 75,
            "color_temp_k": 4200,
            "should_be_on": true,
            "reason": "brightness_ratio"
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    evaluation = svc.evaluate(zone_id)
    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        **evaluation.to_dict(),
    })


# ---- Config Endpoints ------------------------------------------------------


@light_module_bp.route("/config", methods=["GET"])
@require_token
def get_config():
    """Get global light module configuration.

    Response::

        {
            "ok": true,
            "config": {
                "enabled": true,
                "circadian_enabled": true,
                "brightness_ratio_enabled": true,
                "presence_enabled": true,
                ...
            }
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    return jsonify({
        "ok": True,
        "config": svc.get_global_config(),
    })


@light_module_bp.route("/config", methods=["POST"])
@require_token
def update_config():
    """Update global light module configuration (partial update).

    Request body: any subset of global config keys::

        {
            "enabled": true,
            "circadian_enabled": false,
            "outdoor_lux_bright_threshold": 15000
        }

    Response::

        {
            "ok": true,
            "config": { ... }
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    data = request.get_json(silent=True) or {}
    config = svc.update_global_config(data)
    return jsonify({"ok": True, "config": config})


# ---- Sensor Update Endpoints -----------------------------------------------


@light_module_bp.route("/presence/<path:zone_id>", methods=["POST"])
@require_token
def update_presence(zone_id: str):
    """Update presence/motion state for a zone.

    Request body::

        {"detected": true}

    Response::

        {"ok": true, "zone_id": "zone:wohnbereich", "detected": true}
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    data = request.get_json(silent=True) or {}
    detected = bool(data.get("detected", False))
    svc.update_presence(zone_id, detected)

    return jsonify({"ok": True, "zone_id": zone_id, "detected": detected})


@light_module_bp.route("/brightness/<path:zone_id>", methods=["POST"])
@require_token
def update_brightness(zone_id: str):
    """Update brightness sensor readings for a zone.

    Request body::

        {
            "indoor_lux": 250.0,
            "outdoor_lux": 8500.0
        }

    Response::

        {"ok": true, "zone_id": "zone:wohnbereich"}
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    data = request.get_json(silent=True) or {}
    indoor = data.get("indoor_lux")
    outdoor = data.get("outdoor_lux")

    if indoor is not None:
        indoor = float(indoor)
    if outdoor is not None:
        outdoor = float(outdoor)

    svc.update_brightness(zone_id, indoor_lux=indoor, outdoor_lux=outdoor)

    return jsonify({"ok": True, "zone_id": zone_id})


# ---- Apply to HA -----------------------------------------------------------


@light_module_bp.route("/apply/<path:zone_id>", methods=["POST"])
@require_token
def apply_to_ha(zone_id: str):
    """Evaluate zone and apply computed settings to HA lights.

    Calls light.turn_on or light.turn_off via HA Supervisor API.

    Response::

        {
            "ok": true,
            "zone_id": "zone:wohnbereich",
            "applied": {
                "brightness_pct": 75,
                "color_temp_k": 4200,
                "should_be_on": true,
                "reason": "brightness_ratio"
            },
            "lights_controlled": 2,
            "errors": []
        }
    """
    svc = _get_service()
    if svc is None:
        return jsonify({"ok": False, "error": "Light module not initialized"}), 503

    # Evaluate current settings
    evaluation = svc.evaluate(zone_id)
    profile = svc.get_zone_profile(zone_id)

    if profile is None:
        return jsonify({"ok": False, "error": f"Zone '{zone_id}' not found"}), 404

    lights = profile.get("lights", [])
    if not lights:
        return jsonify({
            "ok": True,
            "zone_id": zone_id,
            "applied": evaluation.to_dict(),
            "lights_controlled": 0,
            "errors": ["No lights configured for zone"],
        })

    # Call HA Supervisor API
    ha_url = os.environ.get("SUPERVISOR_API", "http://supervisor/core/api")
    ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not ha_token:
        return jsonify({"ok": False, "error": "No SUPERVISOR_TOKEN available"}), 503

    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }

    errors: list[str] = []
    controlled = 0

    for light_entity in lights:
        try:
            if evaluation.should_be_on:
                service_data: dict[str, Any] = {
                    "entity_id": light_entity,
                    "brightness_pct": evaluation.brightness_pct,
                }
                # Only set color_temp_kelvin if > 0 (some lights may not support it)
                if evaluation.color_temp_k > 0:
                    service_data["color_temp_kelvin"] = evaluation.color_temp_k

                resp = http_requests.post(
                    f"{ha_url}/services/light/turn_on",
                    json=service_data,
                    headers=headers,
                    timeout=5,
                )
                if resp.ok:
                    controlled += 1
                else:
                    errors.append(
                        f"{light_entity}: turn_on returned {resp.status_code}"
                    )
            else:
                resp = http_requests.post(
                    f"{ha_url}/services/light/turn_off",
                    json={"entity_id": light_entity},
                    headers=headers,
                    timeout=5,
                )
                if resp.ok:
                    controlled += 1
                else:
                    errors.append(
                        f"{light_entity}: turn_off returned {resp.status_code}"
                    )
        except Exception as exc:
            errors.append(f"{light_entity}: {exc}")

    return jsonify({
        "ok": True,
        "zone_id": zone_id,
        "applied": evaluation.to_dict(),
        "lights_controlled": controlled,
        "errors": errors,
    })
