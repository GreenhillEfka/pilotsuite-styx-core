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
from copilot_core.module_registry import ModuleRegistry, VALID_STATES, DEFAULT_STATE

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
    "mood_engine": {
        "label": "Mood Engine",
        "fields": [
            {"key": "refresh_interval_seconds", "type": "number", "min": 5, "max": 3600, "label": "Refresh-Intervall (s)"},
            {"key": "min_confidence", "type": "number", "min": 0, "max": 1, "step": 0.01, "label": "Min Confidence"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "neurons": {
        "label": "Neurons",
        "fields": [
            {"key": "pulse_decay_seconds", "type": "number", "min": 1, "max": 600, "label": "Puls-Decays (s)"},
            {"key": "max_active_neurons", "type": "number", "min": 1, "max": 256, "label": "Max aktive Neuronen"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "knowledge_graph": {
        "label": "Knowledge Graph",
        "fields": [
            {"key": "max_nodes", "type": "number", "min": 100, "max": 20000, "label": "Max Nodes"},
            {"key": "max_edges", "type": "number", "min": 100, "max": 50000, "label": "Max Edges"},
            {"key": "prune_interval_minutes", "type": "number", "min": 1, "max": 1440, "label": "Prune-Intervall (min)"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "conversation_memory": {
        "label": "Conversation Memory",
        "fields": [
            {"key": "max_entries", "type": "number", "min": 100, "max": 50000, "label": "Max Eintraege"},
            {"key": "half_life_days", "type": "number", "min": 1, "max": 3650, "label": "Memory Half-Life (Tage)"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "rag_pipeline": {
        "label": "RAG Pipeline",
        "fields": [
            {"key": "chunk_size", "type": "number", "min": 100, "max": 4000, "label": "Chunk-Groesse"},
            {"key": "chunk_overlap", "type": "number", "min": 0, "max": 1000, "label": "Chunk-Overlap"},
            {"key": "min_similarity", "type": "number", "min": 0, "max": 1, "step": 0.01, "label": "Min Similarity"},
            {"key": "max_results", "type": "number", "min": 1, "max": 50, "label": "Max Treffer"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "media_zones": {
        "label": "Media Zones",
        "fields": [
            {"key": "auto_follow_on_presence", "type": "boolean", "label": "Auto-Follow bei Praesenz"},
            {"key": "require_active_playback", "type": "boolean", "label": "Nur aktive Wiedergabe folgen"},
            {"key": "transfer_cooldown_sec", "type": "number", "min": 0, "max": 3600, "label": "Transfer-Cooldown (s)"},
            {"key": "max_zone_hops", "type": "number", "min": 0, "max": 100, "label": "Max Zone-Hops"},
        ],
    },
    "light_intelligence": {
        "label": "Light Intelligence",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Adaptive Steuerung aktiv"},
            {"key": "trigger_mode", "type": "select", "label": "Trigger-Modus", "options": [
                {"value": "time_or_presence", "label": "Zeit oder Praesenz"},
                {"value": "presence_only", "label": "Nur Praesenz"},
                {"value": "time_only", "label": "Nur Zeit"},
            ]},
            {"key": "use_indoor_outdoor_ratio", "type": "boolean", "label": "Innen/Aussen-Verhaeltnis"},
            {"key": "ratio_threshold", "type": "number", "min": 0.01, "max": 1, "step": 0.01, "label": "Ratio-Schwelle"},
            {"key": "dark_outdoor_lux_threshold", "type": "number", "min": 0, "max": 20000, "label": "Aussen dunkel unter (Lux)"},
        ],
    },
    "scene_intelligence": {
        "label": "Scene Intelligence",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Auto-Szenen aktiv"},
            {"key": "min_confidence_auto", "type": "number", "min": 0, "max": 1, "step": 0.01, "label": "Min Confidence Auto"},
            {"key": "require_home_presence", "type": "boolean", "label": "Nur wenn Zuhause"},
            {"key": "allow_night_automation", "type": "boolean", "label": "Nacht-Automation"},
        ],
    },
    "energy_context": {
        "label": "Energy Context",
        "fields": [
            {"key": "refresh_interval_seconds", "type": "number", "min": 5, "max": 3600, "label": "Refresh-Intervall (s)"},
            {"key": "anomaly_threshold", "type": "number", "min": 0, "max": 1, "step": 0.01, "label": "Anomaly-Schwelle"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "weather_context": {
        "label": "Weather Context",
        "fields": [
            {"key": "refresh_interval_seconds", "type": "number", "min": 30, "max": 7200, "label": "Refresh-Intervall (s)"},
            {"key": "warn_on_severe", "type": "boolean", "label": "Warnungen bei schweren Ereignissen"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "network": {
        "label": "Network Context",
        "fields": [
            {"key": "poll_interval_seconds", "type": "number", "min": 5, "max": 3600, "label": "Poll-Intervall (s)"},
            {"key": "latency_warn_ms", "type": "number", "min": 10, "max": 5000, "label": "Latency-Warnschwelle (ms)"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "camera_context": {
        "label": "Camera Context",
        "fields": [
            {"key": "motion_confidence_min", "type": "number", "min": 0, "max": 1, "step": 0.01, "label": "Min Motion-Confidence"},
            {"key": "retention_hours", "type": "number", "min": 1, "max": 168, "label": "Retention (h)"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "user_preferences": {
        "label": "User Preferences",
        "fields": [
            {"key": "learning_rate", "type": "number", "min": 0.001, "max": 1, "step": 0.001, "label": "Learning Rate"},
            {"key": "min_samples", "type": "number", "min": 1, "max": 5000, "label": "Min Samples"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "proactive": {
        "label": "Proactive Engine",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Proaktive Vorschlaege aktiv"},
            {"key": "cooldown_minutes", "type": "number", "min": 0, "max": 1440, "label": "Cooldown (min)"},
            {"key": "max_suggestions_per_hour", "type": "number", "min": 1, "max": 100, "label": "Max Vorschlaege pro Stunde"},
        ],
    },
    "web_search": {
        "label": "Web Search",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Websuche aktiv"},
            {"key": "provider", "type": "text", "label": "Provider"},
            {"key": "timeout_seconds", "type": "number", "min": 1, "max": 60, "label": "Timeout (s)"},
        ],
    },
    "telegram_bot": {
        "label": "Telegram Bot",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Telegram aktiv"},
            {"key": "allowed_chat_ids", "type": "array", "label": "Allowed Chat IDs (CSV)"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "mcp_server": {
        "label": "MCP Server",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "MCP aktiv"},
            {"key": "allow_remote_tools", "type": "boolean", "label": "Remote Tools erlauben"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "waste_reminder": {
        "label": "Waste Reminder",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Erinnerungen aktiv"},
            {"key": "lead_time_hours", "type": "number", "min": 1, "max": 168, "label": "Vorlaufzeit (h)"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
    "birthday_reminder": {
        "label": "Birthday Reminder",
        "fields": [
            {"key": "enabled", "type": "boolean", "label": "Erinnerungen aktiv"},
            {"key": "lead_time_days", "type": "number", "min": 1, "max": 365, "label": "Vorlaufzeit (Tage)"},
            {"key": "notes", "type": "text", "label": "Notizen"},
        ],
    },
}

_MODULE_CATALOG: dict[str, dict[str, str]] = {
    "brain_graph": {
        "label": "Brain Graph",
        "description": "Entity-Beziehungen erkennen und als neuronales Netz visualisieren",
        "category": "core",
    },
    "habitus_miner": {
        "label": "Habitus Miner",
        "description": "Verhaltensmuster (A->B) entdecken",
        "category": "automation",
    },
    "mood_engine": {
        "label": "Mood Engine",
        "description": "Comfort, Joy und Frugality pro Zone bewerten",
        "category": "core",
    },
    "event_forwarder": {
        "label": "Event Bridge",
        "description": "HA-Events in die Core-Pipeline einspeisen",
        "category": "bridge",
    },
    "neurons": {
        "label": "Neurons",
        "description": "Kontext-Neuronen (Praesenz, Wetter, Energie, Medien)",
        "category": "core",
    },
    "knowledge_graph": {
        "label": "Knowledge Graph",
        "description": "Semantische Struktur und Beziehungen",
        "category": "knowledge",
    },
    "conversation_memory": {
        "label": "Conversation Memory",
        "description": "Langzeitgedaechtnis fuer Styx-Dialoge",
        "category": "conversation",
    },
    "rag_pipeline": {
        "label": "RAG Pipeline",
        "description": "Dokument-Indexierung und semantische Suche",
        "category": "conversation",
    },
    "media_zones": {
        "label": "Media Zones",
        "description": "Musikwolke und zonenbasierte Wiedergabe",
        "category": "media",
    },
    "light_intelligence": {
        "label": "Light Intelligence",
        "description": "Adaptive Lichtlogik mit Praesenz- und Lux-Kontext",
        "category": "automation",
    },
    "scene_intelligence": {
        "label": "Scene Intelligence",
        "description": "Szenenvorschlaege und Aktivierungslogik",
        "category": "automation",
    },
    "energy_context": {
        "label": "Energy Context",
        "description": "PV, Netzbezug und Lastkontext",
        "category": "context",
    },
    "weather_context": {
        "label": "Weather Context",
        "description": "Wetterdaten und Warnungen",
        "category": "context",
    },
    "network": {
        "label": "Network Context",
        "description": "UniFi/WLAN/LAN-Qualitaet",
        "category": "context",
    },
    "camera_context": {
        "label": "Camera Context",
        "description": "Kamera-Bewegung/Praesenz als Neuronen-Input",
        "category": "context",
    },
    "user_preferences": {
        "label": "User Preferences",
        "description": "Nutzerpraeferenzen und Profil-Lernen",
        "category": "learning",
    },
    "proactive": {
        "label": "Proactive Engine",
        "description": "Kontextbezogene Vorschlaege",
        "category": "automation",
    },
    "web_search": {
        "label": "Web Search",
        "description": "Web-Recherche, News und Warnungen",
        "category": "conversation",
    },
    "telegram_bot": {
        "label": "Telegram Bot",
        "description": "Externer Chat-/Notification-Kanal",
        "category": "integration",
    },
    "mcp_server": {
        "label": "MCP Server",
        "description": "Tooling fuer externe Agent-Clients",
        "category": "integration",
    },
    "waste_reminder": {
        "label": "Waste Reminder",
        "description": "Abfall-Erinnerungen",
        "category": "assistant",
    },
    "birthday_reminder": {
        "label": "Birthday Reminder",
        "description": "Geburtstags-Erinnerungen",
        "category": "assistant",
    },
}

_MODULE_PRESETS: dict[str, dict[str, Any]] = {
    "balanced_home": {
        "label": "Balanced Home",
        "description": "Sicherer Standard: Kernmodule aktiv, lernende Module im Learning-Modus.",
        "states": {
            "brain_graph": "active",
            "habitus_miner": "learning",
            "mood_engine": "active",
            "event_forwarder": "active",
            "neurons": "active",
            "knowledge_graph": "active",
            "conversation_memory": "active",
            "rag_pipeline": "active",
            "media_zones": "active",
            "light_intelligence": "learning",
            "scene_intelligence": "learning",
            "energy_context": "learning",
            "weather_context": "learning",
            "network": "learning",
            "camera_context": "learning",
            "user_preferences": "learning",
            "proactive": "learning",
            "web_search": "learning",
            "telegram_bot": "off",
            "mcp_server": "active",
            "waste_reminder": "active",
            "birthday_reminder": "active",
        },
        "settings": {
            "habitus_miner": {"min_confidence": 0.7, "auto_apply_threshold": 0.85},
            "event_forwarder": {"flush_interval_seconds": 15, "include_service_calls": True},
            "brain_graph": {"refresh_interval_seconds": 30, "max_nodes": 1200, "max_edges": 3500},
        },
    },
    "privacy_local_first": {
        "label": "Privacy Local-First",
        "description": "Cloud-nahe Module runterfahren, lokale Kernpipeline priorisieren.",
        "states": {
            "brain_graph": "active",
            "habitus_miner": "learning",
            "mood_engine": "active",
            "event_forwarder": "active",
            "neurons": "active",
            "knowledge_graph": "active",
            "conversation_memory": "active",
            "rag_pipeline": "active",
            "media_zones": "active",
            "light_intelligence": "active",
            "scene_intelligence": "learning",
            "energy_context": "learning",
            "weather_context": "learning",
            "network": "learning",
            "camera_context": "learning",
            "user_preferences": "learning",
            "proactive": "learning",
            "web_search": "off",
            "telegram_bot": "off",
            "mcp_server": "active",
            "waste_reminder": "active",
            "birthday_reminder": "active",
        },
        "settings": {
            "event_forwarder": {"include_service_calls": False},
            "habitus_miner": {"min_confidence": 0.75, "auto_apply_threshold": 0.9},
        },
    },
    "autonomous_plus": {
        "label": "Autonomous Plus",
        "description": "Fuer stabile Setups: mehr Module auf active und aggressive Automatisierung.",
        "states": {
            "brain_graph": "active",
            "habitus_miner": "active",
            "mood_engine": "active",
            "event_forwarder": "active",
            "neurons": "active",
            "knowledge_graph": "active",
            "conversation_memory": "active",
            "rag_pipeline": "active",
            "media_zones": "active",
            "light_intelligence": "active",
            "scene_intelligence": "active",
            "energy_context": "active",
            "weather_context": "learning",
            "network": "learning",
            "camera_context": "learning",
            "user_preferences": "active",
            "proactive": "active",
            "web_search": "learning",
            "telegram_bot": "off",
            "mcp_server": "active",
            "waste_reminder": "active",
            "birthday_reminder": "active",
        },
        "settings": {
            "habitus_miner": {"min_confidence": 0.62, "auto_apply_threshold": 0.72},
            "scene_intelligence": {"min_confidence_auto": 0.7, "require_home_presence": True},
            "light_intelligence": {"trigger_mode": "time_or_presence", "use_indoor_outdoor_ratio": True},
        },
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


def _all_known_module_ids(registry: ModuleRegistry) -> list[str]:
    configured = set(registry.get_all_states().keys())
    catalog = set(_MODULE_CATALOG.keys())
    schema_known = set(_MODULE_SETTINGS_SCHEMAS.keys())
    return sorted(configured | catalog | schema_known)


def _module_snapshot(registry: ModuleRegistry, module_id: str) -> dict[str, Any]:
    meta = _MODULE_CATALOG.get(module_id, {})
    return {
        "id": module_id,
        "label": meta.get("label", module_id),
        "description": meta.get("description", ""),
        "category": meta.get("category", "misc"),
        "state": registry.get_state(module_id),
        "default_state": DEFAULT_STATE,
        "settings": registry.get_settings(module_id),
        "schema": _schema_for_module(module_id),
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
    modules = registry.get_all_states()
    include_defaults = str(request.args.get("include_defaults", "")).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not include_defaults:
        return jsonify({"ok": True, "modules": modules})

    effective = {
        module_id: registry.get_state(module_id)
        for module_id in _all_known_module_ids(registry)
    }
    return jsonify(
        {
            "ok": True,
            "modules": modules,
            "effective_modules": effective,
            "default_state": DEFAULT_STATE,
        }
    )


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


@module_control_bp.route("/catalog", methods=["GET"])
@require_token
def get_module_catalog():
    """Return enriched module catalog with effective state/settings."""
    registry = _get_registry()
    modules = [_module_snapshot(registry, module_id) for module_id in _all_known_module_ids(registry)]
    return jsonify(
        {
            "ok": True,
            "count": len(modules),
            "default_state": DEFAULT_STATE,
            "modules": modules,
            "states": {entry["id"]: entry["state"] for entry in modules},
        }
    )


@module_control_bp.route("/presets", methods=["GET"])
@require_token
def list_module_presets():
    """List available module presets."""
    presets = []
    for preset_id, preset in _MODULE_PRESETS.items():
        states = preset.get("states", {})
        settings = preset.get("settings", {})
        presets.append(
            {
                "id": preset_id,
                "label": preset.get("label", preset_id),
                "description": preset.get("description", ""),
                "modules": len(states),
                "settings_overrides": len(settings),
                "states": states,
                "settings": settings,
            }
        )
    return jsonify({"ok": True, "presets": presets, "count": len(presets)})


@module_control_bp.route("/presets/apply", methods=["POST"])
@require_token
def apply_module_preset():
    """Apply a module preset to state + settings registry."""
    registry = _get_registry()
    body = request.get_json(silent=True) or {}

    preset_id = str(body.get("preset_id", "")).strip()
    if not preset_id:
        return jsonify({"ok": False, "error": "Missing 'preset_id'"}), 400

    preset = _MODULE_PRESETS.get(preset_id)
    if not preset:
        return jsonify(
            {
                "ok": False,
                "error": f"Unknown preset '{preset_id}'",
                "available_presets": sorted(_MODULE_PRESETS.keys()),
            }
        ), 404

    dry_run = bool(body.get("dry_run", False))
    merge_settings = bool(body.get("merge_settings", True))
    states = preset.get("states", {})
    settings = preset.get("settings", {})

    if dry_run:
        return jsonify(
            {
                "ok": True,
                "dry_run": True,
                "preset_id": preset_id,
                "label": preset.get("label", preset_id),
                "state_changes": states,
                "settings_changes": settings,
            }
        )

    applied_states: dict[str, str] = {}
    failed_states: dict[str, str] = {}
    for module_id, state in states.items():
        if state not in VALID_STATES:
            failed_states[module_id] = f"invalid_state:{state}"
            continue
        if registry.set_state(module_id, state):
            applied_states[module_id] = state
        else:
            failed_states[module_id] = "persist_failed"

    applied_settings: dict[str, dict[str, Any]] = {}
    failed_settings: dict[str, str] = {}
    for module_id, next_settings in settings.items():
        if not isinstance(next_settings, dict):
            failed_settings[module_id] = "settings_must_be_object"
            continue
        final_settings = dict(next_settings)
        if merge_settings:
            current = registry.get_settings(module_id)
            final_settings = {**current, **next_settings}
        if registry.set_settings(module_id, final_settings):
            applied_settings[module_id] = registry.get_settings(module_id)
        else:
            failed_settings[module_id] = "persist_failed"

    status = 200 if not failed_states and not failed_settings else 207
    return jsonify(
        {
            "ok": True,
            "preset_id": preset_id,
            "label": preset.get("label", preset_id),
            "applied_states": applied_states,
            "failed_states": failed_states,
            "applied_settings": applied_settings,
            "failed_settings": failed_settings,
            "default_state": DEFAULT_STATE,
            "state_count": len(applied_states),
            "settings_count": len(applied_settings),
        }
    ), status
