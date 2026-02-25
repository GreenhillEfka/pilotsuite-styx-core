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
from typing import Any, Optional

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


_MODULE_SETTINGS_SCHEMAS: dict[str, dict[str, Any]] = {
    "brain_graph": {
        "label": "Brain Graph",
        "fields": [
            {"key": "refresh_interval_seconds", "type": "number", "min": 1, "max": 3600, "label": "Refresh-Intervall (s)"},
            {"key": "max_nodes", "type": "number", "min": 50, "max": 5000, "label": "Max Nodes"},
            {"key": "max_edges", "type": "number", "min": 50, "max": 20000, "label": "Max Edges"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "habitus_miner": {
        "label": "Habitus Miner",
        "fields": [
            {"key": "auto_apply_threshold", "type": "number", "min": 0, "max": 1, "step": 0.01, "label": "Auto-Apply Schwellwert"},
            {"key": "min_confidence", "type": "number", "min": 0, "max": 1, "step": 0.01, "label": "Min Confidence"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "event_forwarder": {
        "label": "Event Bridge",
        "fields": [
            {"key": "flush_interval_seconds", "type": "number", "min": 1, "max": 300, "label": "Flush-Intervall (s)"},
            {"key": "max_batch", "type": "number", "min": 1, "max": 5000, "label": "Max Batch"},
            {"key": "include_service_calls", "type": "boolean", "label": "Service-Calls weiterleiten"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
}


def _schema_for_module(module_id: str) -> dict[str, Any]:
    if module_id in _MODULE_SETTINGS_SCHEMAS:
        return _MODULE_SETTINGS_SCHEMAS[module_id]
    return {
        "label": module_id,
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Enabled"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    }


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


@module_control_bp.route("/<module_id>/settings", methods=["GET"])
@require_token
def get_module_settings(module_id: str):
    """Get persisted module settings + schema for dashboard rendering."""
    registry = _get_registry()
    return jsonify(
        {
            "ok": True,
            "module_id": module_id,
            "schema": _schema_for_module(module_id),
            "settings": registry.get_settings(module_id),
            "state": registry.get_state(module_id),
        }
    )


@module_control_bp.route("/<module_id>/settings", methods=["POST"])
@require_token
def set_module_settings(module_id: str):
    """Store module settings."""
    registry = _get_registry()
    data = request.get_json(silent=True) or {}
    settings = data.get("settings", data)
    if not isinstance(settings, dict):
        return jsonify({"ok": False, "error": "settings_must_be_object"}), 400
    success = registry.set_settings(module_id, settings)
    if not success:
        return jsonify({"ok": False, "error": "persist_failed"}), 500
    return jsonify(
        {
            "ok": True,
            "module_id": module_id,
            "settings": registry.get_settings(module_id),
            "schema": _schema_for_module(module_id),
        }
    )
