"""Plugin API — Slice 327 (CORE ONLY).

REST endpoints for plugin management:
  GET  /api/v1/plugins/          — list all discovered plugins
  GET  /api/v1/plugins/<id>      — single plugin details
  POST /api/v1/plugins/          — register a plugin programmatically
  POST /api/v1/plugins/<id>/load     — load a plugin
  POST /api/v1/plugins/<id>/enable  — enable a plugin
  POST /api/v1/plugins/<id>/disable — disable a plugin
  POST /api/v1/plugins/<id>/unload  — unload a plugin
  GET  /api/v1/plugins/<id>/config  — get plugin config
  PUT  /api/v1/plugins/<id>/config  — update plugin config
  GET  /api/v1/plugins/summary     — system-wide plugin summary
  GET  /api/v1/plugins/statistics  — detailed plugin statistics
  GET  /api/v1/plugins/hooks      — list registered hooks
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.plugins.engine import (
    PluginEngine,
    PluginHook,
    PluginStatus,
    create_plugin_engine,
)

logger = logging.getLogger(__name__)
bp = Blueprint("plugins", __name__, url_prefix="/api/v1/plugins")

# ---------------------------------------------------------------------------
# Singleton engine for API use
# ---------------------------------------------------------------------------
_engine: PluginEngine | None = None


def get_engine() -> PluginEngine:
    """Lazily initialise / return the shared plugin engine."""
    global _engine
    if _engine is None:
        _engine = create_plugin_engine()
        _engine.discover_plugins()
    return _engine


# ---------------------------------------------------------------------------
# Discovery / listing
# ---------------------------------------------------------------------------

@bp.route("/", methods=["GET"])
def get_plugins_list():
    """List all discovered plugins."""
    engine = get_engine()
    status_filter = request.args.get("status")

    if status_filter:
        try:
            status_enum = PluginStatus(status_filter)
            plugins = engine.get_all_plugins(status=status_enum)
        except ValueError:
            plugins = engine.get_all_plugins()
    else:
        plugins = engine.get_all_plugins()

    return jsonify({"ok": True, "plugins": plugins, "total": len(plugins)})


@bp.route("/<plugin_id>", methods=["GET"])
def get_plugin(plugin_id: str):
    """Get details for a single plugin."""
    engine = get_engine()
    plugin = engine.get_plugin(plugin_id)

    if plugin is None:
        return jsonify({"ok": False, "error": "Plugin not found"}), 404

    return jsonify({"ok": True, "plugin": plugin})


# ---------------------------------------------------------------------------
# Registration (programmatic)
# ---------------------------------------------------------------------------

@bp.route("/", methods=["POST"])
def register_plugin():
    """Register a plugin programmatically (no file-system required)."""
    engine = get_engine()
    data = request.get_json() or {}

    plugin_id = data.get("plugin_id")
    if not plugin_id:
        return jsonify({"ok": False, "error": "plugin_id is required"}), 400

    manifest = data.get("manifest", {})
    manifest.setdefault("plugin_id", plugin_id)

    ok = engine.register_plugin(plugin_id, manifest)
    if not ok:
        return jsonify({"ok": False, "error": "Plugin already registered"}), 409

    return jsonify({"ok": True, "plugin_id": plugin_id}), 201


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@bp.route("/<plugin_id>/load", methods=["POST"])
def load_plugin(plugin_id: str):
    """Load a plugin's Python module into memory."""
    engine = get_engine()
    ok = engine.load_plugin(plugin_id)
    plugin = engine.get_plugin(plugin_id)

    if not ok:
        return jsonify({
            "ok": False,
            "error": plugin.get("error_message", "Failed to load plugin") if plugin else "Plugin not found",
        }), 400

    return jsonify({"ok": True, "plugin": plugin})


@bp.route("/<plugin_id>/enable", methods=["POST"])
def enable_plugin(plugin_id: str):
    """Enable a plugin (load + activate its hooks)."""
    engine = get_engine()
    data = request.get_json() or {}
    config = data.get("config")

    ok = engine.enable_plugin(plugin_id, config=config)
    plugin = engine.get_plugin(plugin_id)

    if not ok:
        return jsonify({
            "ok": False,
            "error": plugin.get("error_message", "Failed to enable plugin") if plugin else "Plugin not found",
        }), 400

    return jsonify({"ok": True, "plugin": plugin})


@bp.route("/<plugin_id>/disable", methods=["POST"])
def disable_plugin(plugin_id: str):
    """Disable a plugin (deactivate its hooks)."""
    engine = get_engine()
    ok = engine.disable_plugin(plugin_id)
    plugin = engine.get_plugin(plugin_id)

    if not ok:
        return jsonify({
            "ok": False,
            "error": "Plugin could not be disabled (may not be enabled)",
        }), 400

    return jsonify({"ok": True, "plugin": plugin})


@bp.route("/<plugin_id>/unload", methods=["POST"])
def unload_plugin(plugin_id: str):
    """Unload a plugin from memory."""
    engine = get_engine()
    ok = engine.unload_plugin(plugin_id)
    plugin = engine.get_plugin(plugin_id)

    if not ok:
        return jsonify({
            "ok": False,
            "error": "Plugin could not be unloaded",
        }), 400

    return jsonify({"ok": True, "plugin": plugin})


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@bp.route("/<plugin_id>/config", methods=["GET"])
def get_plugin_config(plugin_id: str):
    """Return the current runtime configuration for a plugin."""
    engine = get_engine()
    config = engine.get_plugin_config(plugin_id)

    if config is None:
        return jsonify({"ok": False, "error": "Plugin not found"}), 404

    return jsonify({"ok": True, "plugin_id": plugin_id, "config": config})


@bp.route("/<plugin_id>/config", methods=["PUT", "PATCH"])
def update_plugin_config(plugin_id: str):
    """Merge updates into a plugin's runtime configuration."""
    engine = get_engine()
    data = request.get_json() or {}
    config = data.get("config", data)

    # Remove meta-fields that are not part of plugin config
    config.pop("plugin_id", None)
    config.pop("ok", None)

    ok = engine.update_plugin_config(plugin_id, config)
    if not ok:
        return jsonify({"ok": False, "error": "Plugin not found"}), 404

    return jsonify({"ok": True, "plugin_id": plugin_id, "config": engine.get_plugin_config(plugin_id)})


# ---------------------------------------------------------------------------
# System / admin
# ---------------------------------------------------------------------------

@bp.route("/summary", methods=["GET"])
def get_plugin_summary():
    """Return system-wide plugin summary."""
    engine = get_engine()
    return jsonify({"ok": True, **engine.get_plugin_summary()})


@bp.route("/statistics", methods=["GET"])
def get_plugin_statistics():
    """Return detailed plugin statistics."""
    engine = get_engine()
    return jsonify({"ok": True, **engine.get_statistics()})


@bp.route("/hooks", methods=["GET"])
def get_hooks():
    """List all registered hooks, optionally filtered by type."""
    engine = get_engine()
    hook_type = request.args.get("type")
    hooks = engine.get_hooks(hook_type=hook_type)
    return jsonify({"ok": True, "hooks": hooks, "total": len(hooks)})


@bp.route("/hooks", methods=["POST"])
def register_hook():
    """Register a runtime hook programmatically (not tied to a plugin)."""
    engine = get_engine()
    data = request.get_json() or {}

    hook_type_str = data.get("hook_type")
    callback = data.get("callback")  # For manual registration, caller must pass a callable
    priority = data.get("priority", 0)

    if not hook_type_str:
        return jsonify({"ok": False, "error": "hook_type is required"}), 400

    try:
        hook_type = PluginHook(hook_type_str)
    except ValueError:
        return jsonify({"ok": False, "error": f"Unknown hook type: {hook_type_str}"}), 400

    # Runtime hook without a real callback — return error for clarity
    if callback is None:
        return jsonify({
            "ok": False,
            "error": "callback must be a JSON-serializable function reference — use the engine directly for programmatic hook registration",
        }), 400

    hook_id = engine.register_hook(hook_type, callback, priority=priority, plugin_id="runtime")
    return jsonify({"ok": True, "hook_id": hook_id}), 201


@bp.route("/hooks/<hook_id>", methods=["DELETE"])
def unregister_hook(hook_id: str):
    """Unregister a runtime hook by its ID."""
    engine = get_engine()
    ok = engine.unregister_hook(hook_id)

    if not ok:
        return jsonify({"ok": False, "error": "Hook not found"}), 404

    return jsonify({"ok": True})


@bp.route("/discovery", methods=["POST"])
def trigger_discovery():
    """Re-scan plugin directories and refresh the plugin registry."""
    engine = get_engine()
    count = engine.discover_plugins()
    return jsonify({"ok": True, "discovered": int(count)})
