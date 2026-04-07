"""
Module Control API -- Configure module states via REST.

Endpoints:
  GET    /api/v1/modules                   -- List all module states
  GET    /api/v1/modules/<id>              -- Get single module state
  POST   /api/v1/modules                   -- Create new module state
  PUT    /api/v1/modules/<id>              -- Update module state (replace)
  POST   /api/v1/modules/<id>/configure    -- Set module state (PATCH-like)
  DELETE /api/v1/modules/<id>              -- Remove module state from registry
  GET    /api/v1/modules/zones/<zone>      -- List all zone-level overrides
  GET    /api/v1/modules/zones/<zone>/<id> -- Get effective zone module state
  PUT    /api/v1/modules/zones/<zone>/<id> -- Create/update zone override
  DELETE /api/v1/modules/zones/<zone>/<id> -- Remove zone override

All endpoints require a valid auth token (Bearer or X-Auth-Token).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, Response, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.module_registry import DEFAULT_STATE, ModuleRegistry, VALID_STATES

_LOGGER = logging.getLogger(__name__)

module_control_bp = Blueprint("module_control", __name__, url_prefix="/api/v1/modules")

_registry: Optional[ModuleRegistry] = None


def init_module_control_api(registry: ModuleRegistry) -> None:
    """Wire the ModuleRegistry instance into the blueprint."""
    global _registry
    _registry = registry
    _LOGGER.info("Module Control API initialized")


def _get_registry() -> ModuleRegistry:
    """Return the active registry or fall back to the singleton."""
    if _registry is not None:
        return _registry
    return ModuleRegistry.get_instance()


def _error(message: str, status_code: int) -> tuple[Response, int]:
    return jsonify({"ok": False, "error": message}), status_code


def _json_object_from_request() -> tuple[dict[str, Any] | None, tuple[Response, int] | None]:
    data = request.get_json(silent=True)
    if data is None:
        return None, _error("No JSON body provided", 400)
    if not isinstance(data, dict):
        return None, _error("JSON body must be an object", 400)
    return data, None


def _validated_state(data: dict[str, Any]) -> tuple[str | None, tuple[Response, int] | None]:
    raw_state = data.get("state")
    if raw_state is None:
        return None, _error("Missing 'state' in request body", 400)
    if not isinstance(raw_state, str):
        return None, _error("state must be a string", 400)

    new_state = raw_state.strip().lower()
    if not new_state:
        return None, _error("Missing 'state' in request body", 400)

    if new_state not in VALID_STATES:
        return (
            None,
            (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Invalid state '{new_state}'",
                        "valid_states": sorted(VALID_STATES),
                    }
                ),
                422,
            ),
        )

    return new_state, None


def _validated_module_id(data: dict[str, Any]) -> tuple[str | None, tuple[Response, int] | None]:
    raw_module_id = data.get("module_id")
    if raw_module_id is None:
        return None, _error("Missing 'module_id' in request body", 400)
    if not isinstance(raw_module_id, str):
        return None, _error("module_id must be a string", 400)

    module_id = raw_module_id.strip()
    if not module_id:
        return None, _error("Missing 'module_id' in request body", 400)

    return module_id, None


def _zone_override_payload(registry: ModuleRegistry, zone_id: str, module_id: str) -> dict[str, Any]:
    overrides = registry.get_zone_states(zone_id)
    override_state = overrides.get(module_id)
    global_state = registry.get_state(module_id)
    return {
        "zone_id": zone_id,
        "module_id": module_id,
        "state": override_state or global_state,
        "global_state": global_state,
        "override_state": override_state,
        "has_override": override_state is not None,
    }


@module_control_bp.route("", methods=["GET"])
@require_token
def list_modules():
    """Return all explicitly-configured module states."""
    try:
        registry = _get_registry()
        return jsonify({"ok": True, "modules": registry.get_all_states()})
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to list module states")
        return _error(str(exc), 500)


@module_control_bp.route("/zones/<zone_id>", methods=["GET"])
@require_token
def list_zone_modules(zone_id: str):
    """Return all explicit zone-level module state overrides for one zone."""
    try:
        registry = _get_registry()
        return jsonify({"ok": True, "zone_id": zone_id, "overrides": registry.get_zone_states(zone_id)})
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to list zone module states for %s", zone_id)
        return _error(str(exc), 500)


@module_control_bp.route("/zones/<zone_id>/<module_id>", methods=["GET"])
@require_token
def get_zone_module(zone_id: str, module_id: str):
    """Return effective state + override metadata for one zone/module pair."""
    try:
        registry = _get_registry()
        return jsonify({"ok": True, **_zone_override_payload(registry, zone_id, module_id)})
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to get zone module state for %s/%s", zone_id, module_id)
        return _error(str(exc), 500)


@module_control_bp.route("/<module_id>", methods=["GET"])
@require_token
def get_module(module_id: str):
    """Return the state of a single module."""
    try:
        registry = _get_registry()
        state = registry.get_state(module_id)
        return jsonify({"ok": True, "module_id": module_id, "state": state})
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to get module state for %s", module_id)
        return _error(str(exc), 500)


@module_control_bp.route("/<module_id>/configure", methods=["POST"])
@require_token
def configure_module(module_id: str):
    """Set the state of a module."""
    data, error = _json_object_from_request()
    if error:
        return error

    new_state, error = _validated_state(data)
    if error:
        return error

    try:
        registry = _get_registry()
        previous = registry.get_state(module_id)
        success = registry.set_state(module_id, new_state)
        if not success:
            return _error("Failed to persist module state", 500)

        return jsonify(
            {
                "ok": True,
                "module_id": module_id,
                "state": new_state,
                "previous": previous,
            }
        )
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to configure module %s", module_id)
        return _error(str(exc), 500)


@module_control_bp.route("", methods=["POST"])
@require_token
def create_module():
    """Create or update a module state."""
    data, error = _json_object_from_request()
    if error:
        return error

    module_id, error = _validated_module_id(data)
    if error:
        return error

    new_state, error = _validated_state(data)
    if error:
        return error

    try:
        registry = _get_registry()
        all_states = registry.get_all_states()
        was_created = module_id not in all_states
        success = registry.set_state(module_id, new_state)
        if not success:
            return _error("Failed to persist module state", 500)

        return jsonify(
            {
                "ok": True,
                "module_id": module_id,
                "state": new_state,
                "action": "created" if was_created else "updated",
            }
        )
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to create/update module %s", module_id)
        return _error(str(exc), 500)


@module_control_bp.route("/<module_id>", methods=["PUT"])
@require_token
def update_module(module_id: str):
    """Update a module state (full replace)."""
    data, error = _json_object_from_request()
    if error:
        return error

    new_state, error = _validated_state(data)
    if error:
        return error

    try:
        registry = _get_registry()
        previous = registry.get_state(module_id)
        was_created = module_id not in registry.get_all_states()
        success = registry.set_state(module_id, new_state)
        if not success:
            return _error("Failed to persist module state", 500)

        return jsonify(
            {
                "ok": True,
                "module_id": module_id,
                "state": new_state,
                "previous": previous,
                "action": "created" if was_created else "updated",
            }
        )
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to update module %s", module_id)
        return _error(str(exc), 500)


@module_control_bp.route("/<module_id>", methods=["DELETE"])
@require_token
def delete_module(module_id: str):
    """Remove a module state from the registry."""
    try:
        registry = _get_registry()
        all_states = registry.get_all_states()
        if module_id not in all_states:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Module '{module_id}' has no explicit state to delete",
                        "module_id": module_id,
                    }
                ),
                404,
            )

        current_state = registry.get_state(module_id)
        success = registry.delete_state(module_id)
        if not success:
            return _error(f"Failed to delete state for module '{module_id}'", 500)

        _LOGGER.info("Module %s state deleted (was: %s)", module_id, current_state)
        return jsonify({"ok": True, "module_id": module_id, "deleted_state": current_state})
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to delete module %s", module_id)
        return _error(str(exc), 500)


@module_control_bp.route("/zones/<zone_id>/<module_id>", methods=["PUT"])
@require_token
def update_zone_module(zone_id: str, module_id: str):
    """Create or update a zone-level module state override."""
    data, error = _json_object_from_request()
    if error:
        return error

    new_state, error = _validated_state(data)
    if error:
        return error

    try:
        registry = _get_registry()
        previous = _zone_override_payload(registry, zone_id, module_id)
        was_created = not previous["has_override"]
        success = registry.set_zone_state(zone_id, module_id, new_state)
        if not success:
            return _error("Failed to persist zone module state", 500)

        return jsonify(
            {
                "ok": True,
                "zone_id": zone_id,
                "module_id": module_id,
                "state": new_state,
                "previous": previous["state"],
                "previous_override": previous["override_state"],
                "action": "created" if was_created else "updated",
            }
        )
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to update zone module %s/%s", zone_id, module_id)
        return _error(str(exc), 500)


@module_control_bp.route("/zones/<zone_id>/<module_id>", methods=["DELETE"])
@require_token
def delete_zone_module(zone_id: str, module_id: str):
    """Remove a zone-level module state override and fall back to global state."""
    try:
        registry = _get_registry()
        previous = _zone_override_payload(registry, zone_id, module_id)
        if not previous["has_override"]:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Zone module '{zone_id}/{module_id}' has no explicit state to delete",
                        "zone_id": zone_id,
                        "module_id": module_id,
                    }
                ),
                404,
            )

        success = registry.delete_zone_state(zone_id, module_id)
        if not success:
            return _error(f"Failed to delete zone state for '{zone_id}/{module_id}'", 500)

        return jsonify(
            {
                "ok": True,
                "zone_id": zone_id,
                "module_id": module_id,
                "deleted_state": previous["override_state"],
                "effective_state": registry.get_state(module_id),
            }
        )
    except Exception as exc:  # pragma: no cover - contract-tested via API harness
        _LOGGER.exception("Failed to delete zone module %s/%s", zone_id, module_id)
        return _error(str(exc), 500)
