"""Plugin SDK API — v1.0.0 (F7.1).

First-class plugin registry API surface for external extensions.
Enables plugin registration, activation, listing, and status queries.

GET  /api/v1/plugins              — list all plugins (summary)
GET  /api/v1/plugins/{plugin_id}  — get plugin detail
POST /api/v1/plugins/register      — register a new plugin manifest
POST /api/v1/plugins/{plugin_id}/activate   — activate plugin
POST /api/v1/plugins/{plugin_id}/deactivate — deactivate plugin
"""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from copilot_core.api.security import require_token
from copilot_core.hub.plugin_manager import (
    PluginManager,
    PluginManifest,
)

_LOGGER = logging.getLogger(__name__)
bp = Blueprint("plugins_v1", __name__, url_prefix="/api/v1/plugins")

# Singleton manager (same instance used across app lifecycle)
_plugin_manager: PluginManager | None = None


def _manager() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


@bp.route("", methods=["GET"])
@require_token
def list_plugins():
    """List all registered plugins with summary info."""
    mgr = _manager()
    manifests = mgr.list_manifests()
    states = mgr._states  # noqa: SLF001 — internal state dict

    plugins = []
    for mid in manifests:
        manifest = manifests[mid]
        state = states.get(mid)
        plugins.append({
            "plugin_id": mid,
            "name": manifest.name,
            "version": manifest.version,
            "category": manifest.category,
            "status": state.status if state else "unknown",
            "author": manifest.author,
            "description": manifest.description,
        })

    return jsonify({
        "ok": True,
        "version": 1,
        "total": len(plugins),
        "plugins": plugins,
    })


@bp.route("/<plugin_id>", methods=["GET"])
@require_token
def get_plugin(plugin_id: str):
    """Get detailed info for one plugin."""
    mgr = _manager()
    plugin = mgr.get_plugin(plugin_id)
    if plugin is None:
        return jsonify({"ok": False, "error": "plugin not found"}), 404

    return jsonify({"ok": True, "version": 1, "plugin": plugin})


@bp.route("/register", methods=["POST"])
@require_token
def register_plugin():
    """Register a new plugin from manifest JSON."""
    payload = request.get_json()
    if not payload:
        return jsonify({"ok": False, "error": "JSON body required"}), 400

    required = ["plugin_id", "name", "version"]
    for field in required:
        if field not in payload:
            return jsonify({"ok": False, "error": f"missing field: {field}"}), 400

    manifest = PluginManifest(
        plugin_id=payload["plugin_id"],
        name=payload["name"],
        version=payload["version"],
        author=payload.get("author", ""),
        description=payload.get("description", ""),
        category=payload.get("category", "general"),
        icon=payload.get("icon", "mdi:puzzle"),
        requires=payload.get("requires", []),
        provides=payload.get("provides", []),
        config_schema=payload.get("config_schema", {}),
    )

    success = _manager().register_plugin(manifest)
    if not success:
        return jsonify({
            "ok": False,
            "error": "plugin_id already registered or dependency missing",
        }), 409

    _LOGGER.info("Plugin registered: %s v%s", manifest.plugin_id, manifest.version)
    return jsonify({"ok": True, "plugin_id": manifest.plugin_id}), 201


@bp.route("/<plugin_id>/activate", methods=["POST"])
@require_token
def activate_plugin(plugin_id: str):
    """Activate a registered plugin."""
    success = _manager().activate_plugin(plugin_id)
    if not success:
        state = _manager()._states.get(plugin_id)  # noqa: SLF001
        msg = state.error if state and state.error else "activation failed"
        return jsonify({"ok": False, "error": msg}), 400

    _LOGGER.info("Plugin activated: %s", plugin_id)
    return jsonify({"ok": True, "plugin_id": plugin_id})


@bp.route("/<plugin_id>/deactivate", methods=["POST"])
@require_token
def deactivate_plugin(plugin_id: str):
    """Deactivate an active plugin."""
    success = _manager().deactivate_plugin(plugin_id)
    if not success:
        return jsonify({"ok": False, "error": "deactivation failed"}), 400

    _LOGGER.info("Plugin deactivated: %s", plugin_id)
    return jsonify({"ok": True, "plugin_id": plugin_id})

@bp.route("/<plugin_id>/update", methods=["POST"])
@require_token
def update_plugin(plugin_id: str):
    """Update a plugin to a new version (F7.2-A)."""
    payload = request.get_json() or {}
    new_version = payload.get("version")
    if not new_version:
        return jsonify({"ok": False, "error": "version field required"}), 400

    success = _manager().update_plugin(plugin_id, new_version)
    if not success:
        return jsonify({"ok": False, "error": "plugin not found"}), 404

    _LOGGER.info("Plugin updated: %s -> %s", plugin_id, new_version)
    return jsonify({"ok": True, "plugin_id": plugin_id, "version": new_version})


@bp.route("/<plugin_id>/resolve", methods=["GET"])
@require_token
def resolve_plugin(plugin_id: str):
    """Resolve plugin dependency graph and return full status (F7.2-B)."""
    result = _manager().resolve_plugin(plugin_id)
    if result is None:
        return jsonify({"ok": False, "error": "plugin not found"}), 404

    return jsonify({"ok": True, "plugin_id": plugin_id, "resolve": result})
