"""Backend UI API — Data endpoints for 10-tab Backend UI.

Provides structured data for each backend tab:
1. Dashboard (Info-Übersicht, Status)
2. Zonen (Habituszonen, Entity-Mapping, Module pro Zone)
3. Module (Alle Module, Konfiguration, active/learning/off)
4. Brain (Neuronen, Graph, Pipeline)
5. Mood (6 States, 5 Dimensions, History)
6. Automation (Vorschläge, Regeln, History)
7. RAG (Vector-Store, Embeddings, Search, SearXNG, Voice)
8. Media (Sonos, Musikwolke, Favorites, Camera)
9. Hardware (Zigbee, Z-Wave, UniFi, Camera)
10. System (Health, Config, Logs, Models, Docs)
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify
from typing import Any, Dict, List
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)

backend_ui_bp = Blueprint("backend_ui", __name__, url_prefix="/api/v1/backend")


# =============================================================================
# Tab 1: Dashboard
# =============================================================================

@backend_ui_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    """Dashboard data — Info-Übersicht, System-Status."""
    return jsonify({
        "system": {
            "status": "healthy",
            "uptime_hours": 48.5,
            "version": "15.3.0",
            "core_version": "15.2.93",
            "ha_version": "15.2.10",
        },
        "stats": {
            "zones": 10,
            "modules": 25,
            "entities": 150,
            "automations": 45,
            "proposals_pending": 3,
        },
        "health": {
            "cpu_usage": 15.2,
            "memory_usage": 42.8,
            "disk_usage": 65.0,
            "zigbee_health": "good",
            "zwave_health": "good",
            "unifi_health": "good",
        },
        "quick_actions": [
            {"id": "restart_core", "label": "Core neu starten", "icon": "mdi:restart"},
            {"id": "sync_zones", "label": "Zonen synchronisieren", "icon": "mdi:sync"},
            {"id": "clear_cache", "label": "Cache leeren", "icon": "mdi:delete"},
        ],
    })


# =============================================================================
# Tab 2: Zonen
# =============================================================================

@backend_ui_bp.route("/zones", methods=["GET"])
def get_zones():
    """Zones data — Habituszonen, Entity-Mapping, Module pro Zone."""
    return jsonify({
        "zones": [
            {
                "zone_id": "living",
                "zone_type": "living",
                "name": "Wohnbereich",
                "icon": "mdi:sofa",
                "mode": "active",  # active, idle, sleeping, party, away
                "rooms": ["wohnzimmer", "esszimmer"],
                "entity_count": 25,
                "enabled_modules": ["light", "motion", "music", "climate"],
                "module_states": {
                    "light": "active",
                    "motion": "active",
                    "music": "learning",
                    "climate": "active",
                },
                "musicwolke": {
                    "enabled": True,
                    "sonos_favorites": ["Jazz", "Chillout"],
                    "player": "sonos_wohnzimmer",
                    "volume": 40,
                },
            },
            {
                "zone_id": "bath",
                "zone_type": "bath",
                "name": "Badbereich",
                "icon": "mdi:shower-head",
                "mode": "active",
                "rooms": ["bad_og", "gaeste_wc"],
                "entity_count": 12,
                "enabled_modules": ["light", "motion", "climate", "humidity"],
                "module_states": {
                    "light": "active",
                    "motion": "active",
                    "climate": "learning",
                    "humidity": "active",
                },
                "musicwolke": {
                    "enabled": False,
                    "sonos_favorites": [],
                    "player": None,
                    "volume": 0,
                },
            },
            # ... mehr Zonen
        ],
        "zone_types": [
            {"id": "living", "name": "Wohnbereich", "icon": "mdi:sofa"},
            {"id": "bath", "name": "Badbereich", "icon": "mdi:shower-head"},
            {"id": "kitchen", "name": "Kochbereich", "icon": "mdi:stove"},
            {"id": "office", "name": "Bürobereich", "icon": "mdi:desk"},
            {"id": "hallway", "name": "Flur/Durchgang", "icon": "mdi:door-open"},
            {"id": "bedroom", "name": "Schlafbereich", "icon": "mdi:bed"},
            {"id": "room_mira", "name": "Kinderzimmer Mira", "icon": "mdi:baby-face-outline"},
            {"id": "room_paul", "name": "Kinderzimmer Paul", "icon": "mdi:teddy-bear"},
            {"id": "terrace", "name": "Terrasse/Balkon", "icon": "mdi:tree"},
            {"id": "outside", "name": "Außenbereich", "icon": "mdi:home-outline"},
        ],
        "zone_modes": [
            {"id": "active", "name": "Aktiv", "icon": "mdi:play"},
            {"id": "idle", "name": "Inaktiv", "icon": "mdi:pause"},
            {"id": "sleeping", "name": "Schlafmodus", "icon": "mdi:sleep"},
            {"id": "party", "name": "Party", "icon": "mdi:party-popper"},
            {"id": "away", "name": "Abwesend", "icon": "mdi:home-outline"},
        ],
    })


@backend_ui_bp.route("/zones/<zone_id>/entities", methods=["GET"])
def get_zone_entities(zone_id: str):
    """Zone entity mapping."""
    return jsonify({
        "zone_id": zone_id,
        "entities": [
            {"entity_id": "light.wohnzimmer_haupt", "domain": "light", "tags": ["zone_living", "auto_assign"]},
            {"entity_id": "binary_sensor.wohnzimmer_motion", "domain": "motion", "tags": ["zone_living", "auto_assign"]},
            # ... mehr Entities
        ],
        "unassigned_entities": [
            {"entity_id": "light.neuer_sensor", "domain": "light", "suggested_zone": "living"},
        ],
    })


@backend_ui_bp.route("/zones/<zone_id>/modules", methods=["POST"])
def update_zone_module(zone_id: str):
    """Update zone module state (active/learning/off)."""
    from flask import request
    data = request.get_json()
    module_id = data.get("module_id")
    state = data.get("state")  # active, learning, off
    
    # TODO: Update ModuleRegistry
    _LOGGER.info(f"Zone {zone_id} module {module_id} set to {state}")
    
    return jsonify({"success": True, "zone_id": zone_id, "module_id": module_id, "state": state})


# =============================================================================
# Tab 3: Module
# =============================================================================

@backend_ui_bp.route("/modules", methods=["GET"])
def get_modules():
    """All modules with configuration and state."""
    return jsonify({
        "modules": [
            {
                "module_id": "presence",
                "name": "Presence Intelligence",
                "description": "Person-Tracking, Room-Transitions, Occupancy",
                "category": "domain",
                "state": "active",  # active, learning, off
                "config_schema": {
                    "presence_hold_minutes": {"type": "int", "default": 5},
                    "auto_off_minutes": {"type": "int", "default": 10},
                },
                "config": {
                    "presence_hold_minutes": 5,
                    "auto_off_minutes": 10,
                },
                "dependencies": [],
                "zones_enabled": 10,
            },
            {
                "module_id": "light",
                "name": "Light Intelligence",
                "description": "Adaptive Lighting, Scenes, Sun-Tracking",
                "category": "domain",
                "state": "active",
                "config_schema": {
                    "scene_default": {"type": "string", "default": "relax"},
                    "brightness_max": {"type": "int", "default": 100},
                },
                "config": {
                    "scene_default": "relax",
                    "brightness_max": 100,
                },
                "dependencies": ["presence", "timeofday"],
                "zones_enabled": 10,
            },
            # ... mehr Module
        ],
        "categories": [
            {"id": "domain", "name": "Domain Modules"},
            {"id": "intelligence", "name": "Intelligence"},
            {"id": "automation", "name": "Automation"},
            {"id": "media", "name": "Media"},
            {"id": "system", "name": "System"},
        ],
        "states": [
            {"id": "active", "name": "Aktiv", "description": "Voll betriebsbereit"},
            {"id": "learning", "name": "Lernend", "description": "Beobachtet, schlägt vor"},
            {"id": "off", "name": "Aus", "description": "Deaktiviert"},
        ],
    })


@backend_ui_bp.route("/modules/<module_id>", methods=["PUT"])
def update_module(module_id: str):
    """Update module state or config."""
    from flask import request
    data = request.get_json()
    
    # TODO: Update ModuleRegistry
    if "state" in data:
        _LOGGER.info(f"Module {module_id} state set to {data['state']}")
    
    if "config" in data:
        _LOGGER.info(f"Module {module_id} config updated: {data['config']}")
    
    return jsonify({"success": True, "module_id": module_id})


# =============================================================================
# Tab 4: Brain
# =============================================================================

@backend_ui_bp.route("/brain", methods=["GET"])
def get_brain():
    """Brain data — Neurons, Graph, Pipeline."""
    return jsonify({
        "neurons": {
            "context": [
                {"id": "presence", "name": "Presence", "value": 0.8, "firing": True},
                {"id": "timeofday", "name": "Time of Day", "value": 0.6, "firing": False},
                {"id": "lightlevel", "name": "Light Level", "value": 0.4, "firing": False},
                {"id": "weather", "name": "Weather", "value": 0.9, "firing": True},
            ],
            "state": [
                {"id": "energylevel", "name": "Energy Level", "value": 0.7, "firing": True},
                {"id": "stressindex", "name": "Stress Index", "value": 0.3, "firing": False},
                {"id": "comfortindex", "name": "Comfort Index", "value": 0.8, "firing": True},
            ],
            "mood": [
                {"id": "relax", "name": "Relax", "value": 0.7, "firing": True},
                {"id": "focus", "name": "Focus", "value": 0.4, "firing": False},
                {"id": "active", "name": "Active", "value": 0.6, "firing": False},
                {"id": "sleep", "name": "Sleep", "value": 0.2, "firing": False},
            ],
        },
        "graph": {
            "nodes": 350,
            "edges": 1200,
            "last_update": "2026-04-01T00:30:00Z",
            "svg_url": "/api/v1/graph/snapshot.svg",
        },
        "pipeline": {
            "events_last_hour": 150,
            "patterns_discovered": 5,
            "suggestions_generated": 3,
            "last_run": "2026-04-01T00:29:00Z",
        },
    })


# =============================================================================
# Tab 5: Mood
# =============================================================================

@backend_ui_bp.route("/mood", methods=["GET"])
def get_mood():
    """Mood data — 6 States, 5 Dimensions, History."""
    return jsonify({
        "current": {
            "state": "relax",
            "confidence": 0.85,
            "dimensions": {
                "comfort": 0.8,
                "joy": 0.7,
                "frugality": 0.5,
                "energy": 0.6,
                "focus": 0.4,
            },
        },
        "history": [
            {"timestamp": "2026-04-01T00:00:00Z", "state": "relax", "comfort": 0.8},
            {"timestamp": "2026-03-31T23:00:00Z", "state": "focus", "comfort": 0.6},
            {"timestamp": "2026-03-31T22:00:00Z", "state": "active", "comfort": 0.7},
        ],
        "zones": [
            {"zone_id": "living", "mood": "relax", "confidence": 0.8},
            {"zone_id": "bath", "mood": "relax", "confidence": 0.9},
            {"zone_id": "kitchen", "mood": "active", "confidence": 0.7},
        ],
        "states": [
            {"id": "relax", "name": "Entspannt", "icon": "mdi:sofa"},
            {"id": "focus", "name": "Fokussiert", "icon": "mdi:target"},
            {"id": "active", "name": "Aktiv", "icon": "mdi:run"},
            {"id": "sleep", "name": "Müde", "icon": "mdi:sleep"},
            {"id": "party", "name": "Party", "icon": "mdi:party-popper"},
            {"id": "away", "name": "Abwesend", "icon": "mdi:home-outline"},
        ],
    })


# =============================================================================
# Tab 6: Automation
# =============================================================================

@backend_ui_bp.route("/automation", methods=["GET"])
def get_automation():
    """Automation data — Proposals, Rules, History."""
    return jsonify({
        "proposals": [
            {
                "id": "prop_001",
                "title": "Licht ausschalten wenn niemand im Wohnzimmer",
                "description": "Wenn keine Präsenz für 10 Minuten, Licht ausschalten",
                "confidence": 0.85,
                "status": "pending",  # pending, offered, accepted, rejected
                "created_at": "2026-04-01T00:15:00Z",
                "modules_involved": ["presence", "light"],
                "zone": "living",
            },
            {
                "id": "prop_002",
                "title": "Heizung runter wenn Fenster offen",
                "description": "Fensterkontakt öffnet → Heizung auf Eco",
                "confidence": 0.92,
                "status": "pending",
                "created_at": "2026-04-01T00:10:00Z",
                "modules_involved": ["climate", "contact"],
                "zone": "wohnzimmer",
            },
        ],
        "rules": [
            {
                "id": "rule_001",
                "title": "Abends Licht automatisch an",
                "pattern": "time=evening AND presence=detected → light=on",
                "confidence": 0.95,
                "active": True,
            },
        ],
        "history": [
            {"timestamp": "2026-03-31T23:00:00Z", "action": "accepted", "proposal_id": "prop_000"},
            {"timestamp": "2026-03-31T22:00:00Z", "action": "rejected", "proposal_id": "prop_001"},
        ],
    })


@backend_ui_bp.route("/automation/proposals/<proposal_id>/accept", methods=["POST"])
def accept_proposal(proposal_id: str):
    """Accept proposal."""
    # TODO: Implement
    return jsonify({"success": True, "proposal_id": proposal_id, "action": "accepted"})


@backend_ui_bp.route("/automation/proposals/<proposal_id>/reject", methods=["POST"])
def reject_proposal(proposal_id: str):
    """Reject proposal."""
    # TODO: Implement
    return jsonify({"success": True, "proposal_id": proposal_id, "action": "rejected"})


# =============================================================================
# Tab 7: RAG
# =============================================================================

@backend_ui_bp.route("/rag", methods=["GET"])
def get_rag():
    """RAG data — Vector-Store, Embeddings, Search, SearXNG."""
    return jsonify({
        "vectors": {
            "count": 1500,
            "dimensions": 384,
            "last_index": "2026-04-01T00:00:00Z",
        },
        "embeddings": {
            "recent": [
                {"id": "emb_001", "text": "Licht im Wohnzimmer", "created": "2026-04-01T00:20:00Z"},
                {"id": "emb_002", "text": "Heizung im Bad", "created": "2026-04-01T00:15:00Z"},
            ],
        },
        "search_log": [
            {"query": "Wie schalte ich das Licht ein?", "timestamp": "2026-04-01T00:25:00Z", "results": 5},
            {"query": "Wetter heute", "timestamp": "2026-04-01T00:20:00Z", "results": 3},
        ],
        "searxng": {
            "enabled": True,
            "url": "http://localhost:8080",
            "categories": ["general", "news", "weather"],
        },
        "voice": {
            "enabled": True,
            "model": "whisper",
            "language": "de",
        },
    })


# =============================================================================
# Tab 8: Media
# =============================================================================

@backend_ui_bp.route("/media", methods=["GET"])
def get_media():
    """Media data — Sonos, Musikwolke, Favorites, Camera."""
    return jsonify({
        "sonos": {
            "players": [
                {"id": "sonos_wohnzimmer", "name": "Wohnzimmer", "zone": "living", "status": "playing"},
                {"id": "sonos_kuche", "name": "Küche", "zone": "kitchen", "status": "idle"},
            ],
            "favorites": [
                {"id": "fav_001", "name": "Jazz", "url": "x-rincon-mp3radio://..."},
                {"id": "fav_002", "name": "Chillout", "url": "x-rincon-mp3radio://..."},
            ],
            "http_api": {
                "enabled": True,
                "url": "http://localhost:5005",
            },
        },
        "musikwolke": {
            "enabled": True,
            "zones": [
                {"zone_id": "living", "player": "sonos_wohnzimmer", "favorites": ["Jazz", "Chillout"]},
                {"zone_id": "kitchen", "player": "sonos_kuche", "favorites": ["Pop"]},
            ],
        },
        "cameras": [
            {"id": "cam_001", "name": "Haustür", "zone": "hallway", "status": "recording"},
            {"id": "cam_002", "name": "Garten", "zone": "outside", "status": "idle"},
        ],
    })


# =============================================================================
# Tab 9: Hardware
# =============================================================================

@backend_ui_bp.route("/hardware", methods=["GET"])
def get_hardware():
    """Hardware data — Zigbee, Z-Wave, UniFi, Camera."""
    return jsonify({
        "zigbee": {
            "status": "online",
            "devices": 45,
            "health": "good",
            "network_map_url": "/api/v1/zigbee/map",
        },
        "zwave": {
            "status": "online",
            "devices": 20,
            "health": "good",
            "network_map_url": "/api/v1/zwave/map",
        },
        "unifi": {
            "status": "online",
            "devices": 15,
            "health": "good",
            "network_map_url": "/api/v1/unifi/map",
        },
        "cameras": [
            {"id": "cam_001", "name": "Haustür", "status": "recording", "snapshot_url": "/api/v1/camera/cam_001/snapshot"},
        ],
    })


# =============================================================================
# Tab 10: System
# =============================================================================

@backend_ui_bp.route("/system", methods=["GET"])
def get_system():
    """System data — Health, Config, Logs, Models, Docs."""
    return jsonify({
        "health": {
            "cpu_usage": 15.2,
            "memory_usage": 42.8,
            "disk_usage": 65.0,
            "uptime_hours": 48.5,
        },
        "config": {
            "editable": True,
            "backup_available": True,
        },
        "logs": {
            "lines_available": 1000,
            "log_url": "/api/v1/logs",
        },
        "models": {
            "current": "qwen3.5:397b-cloud",
            "available": [
                {"id": "qwen3.5:397b-cloud", "name": "Qwen 3.5 397B", "recommended": True},
                {"id": "glm-5:cloud", "name": "GLM-5", "recommended": False},
                {"id": "deepseek-v3.2:cloud", "name": "DeepSeek V3.2", "recommended": False},
            ],
            "recommendations": {
                "chat": "qwen3.5:397b-cloud",
                "code": "deepseek-v3.2:cloud",
                "fast": "glm-5:cloud",
            },
        },
        "docs": {
            "installation": "/docs/installation",
            "handbook": "/docs/handbook",
            "api": "/docs/api",
        },
    })


@backend_ui_bp.route("/system/models", methods=["PUT"])
def update_model():
    """Update current LLM model."""
    from flask import request
    data = request.get_json()
    model_id = data.get("model_id")
    
    # TODO: Update model config
    _LOGGER.info(f"Model updated to {model_id}")
    
    return jsonify({"success": True, "model_id": model_id})
