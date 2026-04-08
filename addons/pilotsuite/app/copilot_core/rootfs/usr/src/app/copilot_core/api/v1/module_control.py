"""
Module Control API -- Configure module states via REST.

Endpoints:
  GET  /api/v1/modules              -- List all module states
  GET  /api/v1/modules/<id>         -- Get single module state
  POST /api/v1/modules/<id>/configure -- Set module state

All endpoints require a valid auth token (Bearer or X-Auth-Token).
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.module_registry import ModuleRegistry, VALID_STATES

_LOGGER = logging.getLogger(__name__)

# Blueprint prefix must match dashboard's fetch to /api/v1/modules/...
module_control_bp = Blueprint(
    "module_control", __name__, url_prefix="/api/v1/modules"
)

# Global registry reference, set by init_module_control_api()
_registry: Optional[ModuleRegistry] = None


def init_module_control_api(registry: ModuleRegistry) -> None:
    """Wire the ModuleRegistry instance into the blueprint.

    Called from ``core_setup.register_blueprints()`` (or ``init_services``).
    """
    global _registry
    _registry = registry
    _LOGGER.info("Module Control API initialized")


def _get_registry() -> ModuleRegistry:
    """Return the active registry or fall back to the singleton."""
    if _registry is not None:
        return _registry
    return ModuleRegistry.get_instance()


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@module_control_bp.route("/", methods=["GET"])
@require_token
def list_modules():
    """Return all explicitly-configured module states.

    Response::

        {
            "ok": true,
            "modules": {
                "mood_engine": "active",
                "habitus_miner": "learning",
                ...
            }
        }
    """
    registry = _get_registry()
    return jsonify({"ok": True, "modules": registry.get_all_states()})


@module_control_bp.route("/<module_id>", methods=["GET"])
@require_token
def get_module(module_id: str):
    """Return the state of a single module.

    Modules that have never been configured return ``"active"`` (the default).

    Response::

        {"ok": true, "module_id": "mood_engine", "state": "active"}
    """
    registry = _get_registry()
    state = registry.get_state(module_id)
    return jsonify({"ok": True, "module_id": module_id, "state": state})


@module_control_bp.route("/<module_id>/configure", methods=["POST"])
@require_token
def configure_module(module_id: str):
    """Set the state of a module.

    Request body::

        {"state": "active" | "learning" | "off"}

    Response::

        {
            "ok": true,
            "module_id": "mood_engine",
            "state": "learning",
            "previous": "active"
        }
    """
    registry = _get_registry()

    data = request.get_json(silent=True) or {}
    new_state = data.get("state", "").strip().lower()

    if not new_state:
        return jsonify({
            "ok": False,
            "error": "Missing 'state' in request body",
        }), 400

    if new_state not in VALID_STATES:
        return jsonify({
            "ok": False,
            "error": f"Invalid state '{new_state}'",
            "valid_states": sorted(VALID_STATES),
        }), 422

    previous = registry.get_state(module_id)
    success = registry.set_state(module_id, new_state)

    if not success:
        return jsonify({
            "ok": False,
            "error": "Failed to persist module state",
        }), 500

    return jsonify({
        "ok": True,
        "module_id": module_id,
        "state": new_state,
        "previous": previous,
    })
