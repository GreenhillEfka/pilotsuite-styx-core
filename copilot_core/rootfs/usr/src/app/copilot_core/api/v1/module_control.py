"""
Module Control API -- Configure module states via REST.

Endpoints:
  GET    /api/v1/modules              -- List all module states
  GET    /api/v1/modules/<id>         -- Get single module state
  POST   /api/v1/modules              -- Create new module state
  PUT    /api/v1/modules/<id>         -- Update module state (replace)
  POST   /api/v1/modules/<id>/configure -- Set module state (PATCH-like)
  DELETE /api/v1/modules/<id>         -- Remove module state from registry

All endpoints require a valid auth token (Bearer or X-Auth-Token).
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.module_registry import ModuleRegistry, VALID_STATES, DEFAULT_STATE

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

@module_control_bp.route("", methods=["GET"])
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


# ------------------------------------------------------------------
# Full REST endpoints
# ------------------------------------------------------------------

@module_control_bp.route("", methods=["POST"])
@require_token
def create_module():
    """Create or update a module state.

    This is a PUT-style endpoint that upserts the module state.
    If the module exists, it will be updated (overwrite).
    If the module doesn't exist, it will be created with the given state.

    Request body::

        {"module_id": "new_module", "state": "active" | "learning" | "off"}

    Response::

        {
            "ok": true,
            "module_id": "new_module",
            "state": "learning",
            "action": "created" | "updated"
        }
    """
    registry = _get_registry()

    data = request.get_json(silent=True) or {}
    module_id = data.get("module_id", "").strip()
    new_state = data.get("state", "").strip().lower()

    if not module_id:
        return jsonify({
            "ok": False,
            "error": "Missing 'module_id' in request body",
        }), 400

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

    # Check if module already exists
    existing_state = registry.get_state(module_id)
    was_created = existing_state == DEFAULT_STATE and module_id not in registry.get_all_states()
    
    success = registry.set_state(module_id, new_state)

    if not success:
        return jsonify({
            "ok": False,
            "error": "Failed to persist module state",
        }), 500

    action = "created" if was_created else "updated"

    return jsonify({
        "ok": True,
        "module_id": module_id,
        "state": new_state,
        "action": action,
    })


@module_control_bp.route("/<module_id>", methods=["PUT"])
@require_token
def update_module(module_id: str):
    """Update a module state (full replace).

    This endpoint replaces the module state entirely.
    Unlike POST /<id>/configure, this doesn't require the module_id in the body.

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
    
    # Check if module exists (not just using default)
    all_states = registry.get_all_states()
    was_created = module_id not in all_states

    success = registry.set_state(module_id, new_state)

    if not success:
        return jsonify({
            "ok": False,
            "error": "Failed to persist module state",
        }), 500

    action = "created" if was_created else "updated"

    return jsonify({
        "ok": True,
        "module_id": module_id,
        "state": new_state,
        "previous": previous,
        "action": action,
    })


@module_control_bp.route("/<module_id>", methods=["DELETE"])
@require_token
def delete_module(module_id: str):
    """Remove a module state from the registry.

    This deletes the explicit state, allowing the module to revert to
    its default state (active).

    Response::

        {
            "ok": true,
            "module_id": "mood_engine",
            "deleted_state": "learning"
        }
    """
    registry = _get_registry()

    # Get current state before deletion
    current_state = registry.get_state(module_id)
    
    # Check if module has an explicit state (not default)
    all_states = registry.get_all_states()
    if module_id not in all_states:
        return jsonify({
            "ok": False,
            "error": f"Module '{module_id}' has no explicit state to delete",
            "module_id": module_id,
        }), 404

    # Delete the state by setting it to default and removing from DB
    with registry._lock:
        conn = registry._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM module_states WHERE module_id = ?",
                (module_id,)
            )
            conn.commit()
            deleted_count = cursor.rowcount
        finally:
            conn.close()

    if deleted_count == 0:
        return jsonify({
            "ok": False,
            "error": f"Failed to delete state for module '{module_id}'",
        }), 500

    _LOGGER.info("Module %s state deleted (was: %s)", module_id, current_state)

    return jsonify({
        "ok": True,
        "module_id": module_id,
        "deleted_state": current_state,
    })
