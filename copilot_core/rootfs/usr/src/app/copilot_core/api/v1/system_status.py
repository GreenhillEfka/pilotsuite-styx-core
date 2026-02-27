"""PilotSuite system observability endpoints (status, sensors, host health)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import logging
import os
import platform
import shutil
import time
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

system_status_bp = Blueprint("system_status", __name__, url_prefix="/api/v1/system")

_OVERVIEW_CACHE: dict[str, Any] = {"timestamp": 0.0, "payload": None}
_OVERVIEW_TTL_SECONDS = 15.0

_TRACKED_ENTITY_DOMAINS = {
    "sensor",
    "binary_sensor",
    "number",
    "select",
    "text",
    "switch",
    "button",
}
_SENSOR_DOMAINS = {"sensor", "binary_sensor"}
_UNAVAILABLE_STATES = {"", "unknown", "unavailable", "none", "null"}

_MODULE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("habitus_miner", ("habitus", "zone", "pattern", "regel", "habit")),
    ("brain_graph", ("brain", "graph", "synapse", "neuron")),
    ("mood_engine", ("mood", "comfort", "joy", "frugal", "stress")),
    ("event_forwarder", ("event", "bridge", "forward", "webhook")),
    ("neurons", ("neuron", "context", "state", "pulse")),
    ("knowledge_graph", ("knowledge", "semantic", "entity graph")),
    ("conversation_memory", ("memory", "chat history", "conversation")),
    ("rag_pipeline", ("rag", "document", "embedding", "vector")),
    ("media_zones", ("media", "music", "musikwolke", "player", "sonos", "tv")),
    ("light_intelligence", ("light", "lux", "illuminance", "brightness", "hellig")),
    ("scene_intelligence", ("scene", "preset", "mood scene")),
    ("energy_context", ("energy", "power", "watt", "grid", "pv", "solar")),
    ("weather_context", ("weather", "temperature", "humidity", "wind", "rain")),
    ("network", ("network", "wifi", "lan", "latency", "unifi")),
    ("camera_context", ("camera", "motion", "presence", "face", "object")),
    ("user_preferences", ("user", "profile", "preference", "autonomy")),
    ("proactive", ("proactive", "suggestion", "hint")),
    ("web_search", ("news", "search", "web", "warning", "nina", "dwd")),
    ("telegram_bot", ("telegram",)),
    ("mcp_server", ("mcp", "tool", "openapi")),
    ("waste_reminder", ("waste", "trash", "mull", "abfuhr")),
    ("birthday_reminder", ("birthday", "geburtstag")),
]

_MODULE_FUNCTIONS: dict[str, str] = {
    "habitus_miner": "Lernt Verhaltensmuster und Gewohnheiten",
    "brain_graph": "Visualisiert neuronale Verbindungen und Synapsen",
    "mood_engine": "Berechnet Komfort-/Stimmungsindikatoren",
    "event_forwarder": "Verarbeitet und verteilt HA-Events",
    "neurons": "Kontext-, State- und Mood-Neuronen-Layer",
    "knowledge_graph": "Semantisches Wissensnetz fuer Entitaeten",
    "conversation_memory": "Persistente Chat- und Event-Historie",
    "rag_pipeline": "Dokument-RAG und Retrieval-Kontext",
    "media_zones": "Musikwolke, Multiroom und Zonen-Playback",
    "light_intelligence": "Adaptive Lichtlogik (Zeit/Praesenz/Lux)",
    "scene_intelligence": "Szenenvorschlaege und Szenenautomation",
    "energy_context": "Energiezustand, Last und Verbrauchskontext",
    "weather_context": "Wetter, Warnungen, Umgebungsdaten",
    "network": "Netzwerkzustand und Konnektivitaetsqualitaet",
    "camera_context": "Kamera-/Praesenz-/Bewegungskontext",
    "user_preferences": "Nutzerprofil und Lernpraeferenzen",
    "proactive": "Proaktive Hinweise und Handlungsvorschlaege",
    "web_search": "Web-/News-/Warnungsrecherche",
    "telegram_bot": "Externer Messaging-/Notification-Kanal",
    "mcp_server": "Tool-Expose fuer Agent-/MCP-Clients",
    "waste_reminder": "Muellabfuhr-Erinnerungslogik",
    "birthday_reminder": "Geburtstags- und Kalender-Erinnerungen",
}

_MODULE_NEURON_HINTS: dict[str, list[str]] = {
    "habitus_miner": ["context.activity", "context.presence"],
    "brain_graph": ["context.activity", "state.comfort_level"],
    "mood_engine": ["state.comfort_level", "state.stress_level"],
    "event_forwarder": ["context.activity"],
    "neurons": ["context.activity", "context.presence", "state.energy_level"],
    "knowledge_graph": ["context.activity"],
    "conversation_memory": ["state.comfort_level"],
    "rag_pipeline": ["context.activity"],
    "media_zones": ["context.activity", "state.stimulus_level"],
    "light_intelligence": ["context.light_level", "context.presence"],
    "scene_intelligence": ["context.activity", "state.comfort_level"],
    "energy_context": ["state.energy_level", "state.fatigue_level"],
    "weather_context": ["context.weather", "state.comfort_level"],
    "network": ["context.security"],
    "camera_context": ["context.security", "context.presence"],
    "user_preferences": ["state.comfort_level"],
    "proactive": ["context.presence", "context.activity"],
    "web_search": ["context.activity"],
    "telegram_bot": ["context.activity"],
    "mcp_server": ["context.activity"],
    "waste_reminder": ["context.activity"],
    "birthday_reminder": ["context.activity"],
}

_MODULE_DEPENDENCIES: dict[str, list[str]] = {
    "habitus_miner": ["event_forwarder", "neurons"],
    "brain_graph": ["event_forwarder", "knowledge_graph"],
    "mood_engine": ["neurons", "habitus_miner"],
    "conversation_memory": ["event_forwarder"],
    "rag_pipeline": ["conversation_memory"],
    "media_zones": ["habitus_miner", "proactive"],
    "light_intelligence": ["habitus_miner", "proactive", "weather_context"],
    "scene_intelligence": ["habitus_miner", "light_intelligence", "media_zones"],
    "energy_context": ["neurons"],
    "weather_context": ["neurons"],
    "camera_context": ["event_forwarder", "neurons"],
    "proactive": ["habitus_miner", "neurons"],
    "waste_reminder": ["conversation_memory"],
    "birthday_reminder": ["conversation_memory"],
}

_MODULE_SERVICE_HINTS: dict[str, tuple[str, ...]] = {
    "habitus_miner": ("habitus_service",),
    "brain_graph": ("brain_graph_service",),
    "mood_engine": ("mood_service",),
    "neurons": ("neuron_manager",),
    "knowledge_graph": ("knowledge_graph_service",),
    "conversation_memory": ("conversation_memory",),
    "rag_pipeline": ("vector_store", "embedding_engine"),
    "media_zones": ("media_engine",),
    "light_intelligence": ("light_engine",),
    "scene_intelligence": ("scene_engine",),
    "energy_context": ("energy_advisor",),
    "weather_context": ("weather_context_service",),
    "network": ("network_service", "unifi_service"),
    "camera_context": ("camera_service",),
    "user_preferences": ("user_preference_service",),
    "proactive": ("proactive_service",),
    "web_search": ("web_search_service",),
    "telegram_bot": ("telegram_service",),
    "mcp_server": ("mcp_server",),
    "waste_reminder": ("waste_service",),
    "birthday_reminder": ("birthday_service",),
}

_CRITICAL_SERVICES = (
    "module_registry",
    "neuron_manager",
    "brain_graph_service",
    "conversation_memory",
    "vector_store",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_arg(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _is_available_state(state: Any) -> bool:
    return str(state or "").strip().lower() not in _UNAVAILABLE_STATES


def _fetch_home_assistant_states() -> list[dict[str, Any]]:
    try:
        from copilot_core.hub import api as hub_api

        data = hub_api._fetch_supervisor_states()
        if isinstance(data, list):
            return data
    except Exception:
        logger.debug("Could not fetch HA states from hub API", exc_info=True)
    return []


def _normalize_text(entity_id: str, friendly_name: str) -> str:
    return f"{entity_id} {friendly_name}".lower().replace("-", " ")


def _infer_module_hint(entity_id: str, friendly_name: str) -> str:
    text = _normalize_text(entity_id, friendly_name)
    for module_id, keywords in _MODULE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return module_id
    return "neurons"


def _infer_role(entity_id: str, friendly_name: str) -> str:
    text = _normalize_text(entity_id, friendly_name)
    if any(token in text for token in ("motion", "bewegung", "presence", "occupancy")):
        return "motion"
    if any(token in text for token in ("brightness", "lux", "illuminance", "hellig")):
        return "brightness"
    if any(token in text for token in ("temperature", "temp")):
        return "temperature"
    if any(token in text for token in ("humidity", "feuchte")):
        return "humidity"
    if any(token in text for token in ("co2", "carbon")):
        return "co2"
    if any(token in text for token in ("noise", "sound", "laerm", "larm")):
        return "noise"
    if any(token in text for token in ("power", "watt", "energy", "kwh")):
        return "energy"
    if any(token in text for token in ("camera", "door", "lock", "window")):
        return "security"
    return "generic"


def _build_sensor_inventory(states: list[dict[str, Any]], limit_items: int) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    by_domain: Counter[str] = Counter()
    by_module: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total": 0,
            "available": 0,
            "unavailable": 0,
            "neurons": set(),
        }
    )

    for state in states:
        entity_id = str(state.get("entity_id", "")).strip()
        if "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        if domain not in _TRACKED_ENTITY_DOMAINS:
            continue
        lower_entity = entity_id.lower()
        if (
            "ai_home_copilot" not in lower_entity
            and "pilotsuite" not in lower_entity
            and ".styx_" not in lower_entity
        ):
            continue

        attrs = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
        friendly_name = str(attrs.get("friendly_name", entity_id)).strip()
        module_id = _infer_module_hint(entity_id, friendly_name)
        role = _infer_role(entity_id, friendly_name)
        available = _is_available_state(state.get("state"))
        state_value = str(state.get("state", ""))
        neurons = _MODULE_NEURON_HINTS.get(module_id, ["context.activity"])

        item = {
            "entity_id": entity_id,
            "domain": domain,
            "friendly_name": friendly_name,
            "state": state_value,
            "available": available,
            "module_id": module_id,
            "module_function": _MODULE_FUNCTIONS.get(module_id, "Signal-/Statusauswertung"),
            "role": role,
            "neuron_hints": neurons,
            "unit_of_measurement": attrs.get("unit_of_measurement"),
            "device_class": attrs.get("device_class"),
            "last_changed": state.get("last_changed"),
        }
        items.append(item)

        by_domain[domain] += 1
        row = by_module[module_id]
        row["total"] += 1
        if available:
            row["available"] += 1
        else:
            row["unavailable"] += 1
        row["neurons"].update(neurons)

    items.sort(key=lambda x: (x["module_id"], x["domain"], x["entity_id"]))
    total_entities = len(items)
    available_entities = sum(1 for item in items if item["available"])
    unavailable_entities = total_entities - available_entities
    sensor_count = sum(1 for item in items if item["domain"] in _SENSOR_DOMAINS)
    sensor_available = sum(
        1 for item in items if item["domain"] in _SENSOR_DOMAINS and item["available"]
    )

    module_rows = []
    for module_id, row in by_module.items():
        module_rows.append(
            {
                "module_id": module_id,
                "label": module_id.replace("_", " ").title(),
                "function": _MODULE_FUNCTIONS.get(module_id, "Signal-/Statusauswertung"),
                "total": int(row["total"]),
                "available": int(row["available"]),
                "unavailable": int(row["unavailable"]),
                "neuron_hints": sorted(row["neurons"]),
                "dependencies": _MODULE_DEPENDENCIES.get(module_id, []),
            }
        )
    module_rows.sort(key=lambda row: (-row["total"], row["module_id"]))

    truncated = items[: max(1, min(limit_items, 800))]
    return {
        "total_entities": total_entities,
        "available_entities": available_entities,
        "unavailable_entities": unavailable_entities,
        "availability_ratio": round(available_entities / max(1, total_entities), 4),
        "sensor_count": sensor_count,
        "sensor_available": sensor_available,
        "target_94_reached": sensor_count >= 94,
        "by_domain": dict(sorted(by_domain.items())),
        "by_module": module_rows,
        "items": truncated,
        "items_truncated": len(truncated) < len(items),
    }


def _zone_numeric_average(
    entity_ids: list[str],
    state_map: dict[str, dict[str, Any]],
    keywords: tuple[str, ...],
) -> float | None:
    values: list[float] = []
    for entity_id in entity_ids:
        lowered = entity_id.lower()
        if not any(keyword in lowered for keyword in keywords):
            continue
        entry = state_map.get(entity_id)
        if not entry:
            continue
        value = _safe_float(entry.get("state"))
        if value is None:
            continue
        values.append(value)
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _build_zone_summaries(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from copilot_core.hub import api as hub_api
    except Exception:
        return []

    zone_engine = getattr(hub_api, "_zone_engine", None)
    if zone_engine is None:
        return []

    state_map: dict[str, dict[str, Any]] = {}
    for item in states:
        entity_id = str(item.get("entity_id", "")).strip()
        if entity_id:
            state_map[entity_id] = item

    try:
        overview = zone_engine.get_overview()
        overview_zones = list(getattr(overview, "zones", []) or [])
    except Exception:
        logger.debug("Could not query zone overview", exc_info=True)
        return []

    zone_rows: list[dict[str, Any]] = []
    for zone_item in overview_zones:
        if not isinstance(zone_item, dict):
            continue
        zone_id = str(zone_item.get("zone_id", "")).strip()
        if not zone_id:
            continue
        try:
            detail = zone_engine.get_zone(zone_id) or {}
        except Exception:
            detail = {}

        zone_name = str(zone_item.get("name") or detail.get("name") or zone_id)
        entities = [
            str(entity_id)
            for entity_id in (detail.get("entities") or [])
            if isinstance(entity_id, str) and entity_id
        ]
        entity_count = len(entities)
        available_entities = 0
        unavailable_entities = 0
        motion_active = 0

        for entity_id in entities:
            entry = state_map.get(entity_id)
            if entry and _is_available_state(entry.get("state")):
                available_entities += 1
            else:
                unavailable_entities += 1

            if entity_id.startswith("binary_sensor."):
                lower_eid = entity_id.lower()
                if any(token in lower_eid for token in ("motion", "bewegung", "presence", "occupancy")):
                    state_value = str((entry or {}).get("state", "")).strip().lower()
                    if state_value in {"on", "home", "detected", "occupied", "open"}:
                        motion_active += 1

        try:
            role_map = detail.get("settings", {}).get("entity_roles", {})
            if not isinstance(role_map, dict) or not role_map:
                role_map = hub_api._role_map(entities)
        except Exception:
            role_map = {}

        try:
            deps = hub_api._derive_zone_dependencies(entities, role_map)
        except Exception:
            deps = {"modules": [], "neurons": []}

        summary = {
            "zone_id": zone_id,
            "zone_name": zone_name,
            "entity_count": entity_count,
            "sensor_count": sum(1 for entity_id in entities if entity_id.split(".", 1)[0] in _SENSOR_DOMAINS),
            "available_entities": available_entities,
            "unavailable_entities": unavailable_entities,
            "availability_ratio": round(available_entities / max(1, entity_count), 4),
            "motion_active": motion_active,
            "temperature_avg": _zone_numeric_average(entities, state_map, ("temp", "temperature")),
            "humidity_avg": _zone_numeric_average(entities, state_map, ("humidity", "feuchte")),
            "co2_avg": _zone_numeric_average(entities, state_map, ("co2", "carbon")),
            "brightness_avg": _zone_numeric_average(entities, state_map, ("brightness", "lux", "illuminance", "hellig")),
            "noise_avg": _zone_numeric_average(entities, state_map, ("noise", "sound", "laerm", "larm")),
            "module_dependencies": deps.get("modules", []),
            "neuron_hints": deps.get("neurons", []),
            "standard_metrics_present": {
                "motion": motion_active > 0 or bool(role_map.get("motion")),
                "brightness": bool(role_map.get("brightness")),
                "noise": bool(role_map.get("noise")),
                "humidity": bool(role_map.get("humidity")),
                "heating": bool(role_map.get("heating")),
                "co2": bool(role_map.get("co2")),
                "camera": bool(role_map.get("camera")),
            },
        }
        summary["missing_standard_metrics"] = [
            key for key, present in summary["standard_metrics_present"].items() if not present
        ]
        zone_rows.append(summary)

    zone_rows.sort(key=lambda row: row["zone_name"].lower())
    return zone_rows


def _build_neuron_layer() -> dict[str, Any]:
    try:
        from copilot_core.neurons.manager import get_neuron_manager

        manager = get_neuron_manager()
        summary = manager.get_neuron_summary() or {}
        mood = manager.get_mood_summary() or {}
    except Exception:
        return {
            "available": False,
            "total_neurons": 0,
            "active_neurons": 0,
            "dominant_mood": None,
            "nodes": [],
        }

    nodes: list[dict[str, Any]] = []
    for group in ("context", "state", "mood"):
        raw_items = summary.get(group, {})
        if not isinstance(raw_items, dict):
            continue
        for name, raw in raw_items.items():
            neuron_id = f"{group}.{name}"
            value = 0.0
            if isinstance(raw, dict):
                value = _safe_float(
                    raw.get("value")
                    or raw.get("current_value")
                    or raw.get("score")
                    or raw.get("confidence")
                    or 0.0
                ) or 0.0
            else:
                value = _safe_float(raw) or 0.0

            module_hint = "neurons"
            for module_id, hints in _MODULE_NEURON_HINTS.items():
                if neuron_id in hints:
                    module_hint = module_id
                    break
            nodes.append(
                {
                    "id": neuron_id,
                    "group": group,
                    "value": round(float(value), 4),
                    "active": bool(value >= 0.55),
                    "module_hint": module_hint,
                }
            )

    nodes.sort(key=lambda row: (-float(row["value"]), row["id"]))
    active_count = sum(1 for node in nodes if node["active"])
    return {
        "available": True,
        "total_neurons": len(nodes),
        "active_neurons": active_count,
        "dominant_mood": mood.get("mood") if isinstance(mood, dict) else None,
        "mood_confidence": mood.get("confidence") if isinstance(mood, dict) else None,
        "nodes": nodes[:200],
    }


def _parse_meminfo_mb() -> tuple[float | None, float | None]:
    total_kb = None
    available_kb = None
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        total_kb = float(parts[1])
                elif line.startswith("MemAvailable:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        available_kb = float(parts[1])
                if total_kb is not None and available_kb is not None:
                    break
    except Exception:
        return None, None

    if total_kb is None or available_kb is None:
        return None, None
    total_mb = round(total_kb / 1024.0, 2)
    available_mb = round(available_kb / 1024.0, 2)
    return total_mb, available_mb


def _process_rss_mb() -> float | None:
    try:
        import psutil  # type: ignore

        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
    except Exception:
        pass

    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return round(float(parts[1]) / 1024.0, 2)
    except Exception:
        return None
    return None


def _build_resource_snapshot() -> dict[str, Any]:
    cpu_percent = None
    cpu_count = os.cpu_count()
    memory_total_mb = None
    memory_used_mb = None
    memory_percent = None
    swap_percent = None
    load_avg = None

    try:
        import psutil  # type: ignore

        cpu_percent = round(float(psutil.cpu_percent(interval=0.05)), 2)
        vm = psutil.virtual_memory()
        memory_total_mb = round(float(vm.total) / (1024 * 1024), 2)
        memory_used_mb = round(float(vm.used) / (1024 * 1024), 2)
        memory_percent = round(float(vm.percent), 2)
        swap_percent = round(float(psutil.swap_memory().percent), 2)
    except Exception:
        total_mb, available_mb = _parse_meminfo_mb()
        if total_mb is not None and available_mb is not None:
            used_mb = max(total_mb - available_mb, 0.0)
            memory_total_mb = round(total_mb, 2)
            memory_used_mb = round(used_mb, 2)
            memory_percent = round((used_mb / max(1.0, total_mb)) * 100.0, 2)

    try:
        la1, la5, la15 = os.getloadavg()
        load_avg = {
            "1m": round(float(la1), 3),
            "5m": round(float(la5), 3),
            "15m": round(float(la15), 3),
        }
    except Exception:
        load_avg = None

    storage = {}
    for path in ("/data", "/"):
        try:
            usage = shutil.disk_usage(path)
            used = usage.total - usage.free
            usage_percent = round((used / max(1, usage.total)) * 100.0, 2)
            storage[path] = {
                "total_gb": round(float(usage.total) / (1024 * 1024 * 1024), 2),
                "used_gb": round(float(used) / (1024 * 1024 * 1024), 2),
                "free_gb": round(float(usage.free) / (1024 * 1024 * 1024), 2),
                "usage_percent": usage_percent,
            }
        except Exception:
            continue

    return {
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
            "load_avg": load_avg,
        },
        "memory": {
            "used_mb": memory_used_mb,
            "total_mb": memory_total_mb,
            "percent": memory_percent,
            "swap_percent": swap_percent,
            "process_rss_mb": _process_rss_mb(),
        },
        "storage": storage,
        "host": {
            "hostname": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
    }


def _service_overview(services: dict[str, Any]) -> dict[str, Any]:
    known = sorted(set(_CRITICAL_SERVICES) | set(services.keys()))
    rows = []
    missing_critical = []
    for service_name in known:
        available = services.get(service_name) is not None
        row = {
            "service": service_name,
            "available": available,
            "critical": service_name in _CRITICAL_SERVICES,
        }
        rows.append(row)
        if row["critical"] and not available:
            missing_critical.append(service_name)
    return {
        "count": len(rows),
        "available_count": sum(1 for row in rows if row["available"]),
        "missing_critical": missing_critical,
        "services": rows,
    }


def _module_overview(services: dict[str, Any]) -> dict[str, Any]:
    try:
        from copilot_core.module_registry import ModuleRegistry
        from copilot_core.api.v1 import module_control as module_control_api

        registry = ModuleRegistry.get_instance()
        configured = set(registry.get_all_states().keys())
        known = set(module_control_api._MODULE_CATALOG.keys()) | configured
        module_rows: list[dict[str, Any]] = []
        for module_id in sorted(known):
            state = registry.get_state(module_id)
            settings = registry.get_settings(module_id)
            service_hints = _MODULE_SERVICE_HINTS.get(module_id, ())
            service_ready = True
            if service_hints:
                service_ready = any(services.get(name) is not None for name in service_hints)
            module_rows.append(
                {
                    "id": module_id,
                    "label": module_control_api._MODULE_CATALOG.get(module_id, {}).get(
                        "label", module_id
                    ),
                    "state": state,
                    "configured": bool(settings),
                    "settings_count": len(settings),
                    "service_ready": service_ready,
                    "service_hints": list(service_hints),
                    "dependencies": _MODULE_DEPENDENCIES.get(module_id, []),
                    "neuron_hints": _MODULE_NEURON_HINTS.get(module_id, []),
                }
            )

        return {
            "count": len(module_rows),
            "states": dict(Counter(row["state"] for row in module_rows)),
            "service_ready_count": sum(1 for row in module_rows if row["service_ready"]),
            "modules": module_rows,
        }
    except Exception:
        logger.debug("Could not build module overview", exc_info=True)
        return {
            "count": 0,
            "states": {},
            "service_ready_count": 0,
            "modules": [],
        }


def _overall_health_summary(
    resources: dict[str, Any],
    sensors: dict[str, Any],
    services: dict[str, Any],
    modules: dict[str, Any],
) -> dict[str, Any]:
    score = 100
    issues: list[dict[str, Any]] = []

    cpu_percent = _safe_float(resources.get("cpu", {}).get("percent"))
    if cpu_percent is not None and cpu_percent >= 90:
        score -= 20
        issues.append({"key": "cpu_high", "severity": "high", "detail": f"CPU {cpu_percent:.1f}%"})
    elif cpu_percent is not None and cpu_percent >= 80:
        score -= 10
        issues.append({"key": "cpu_warn", "severity": "medium", "detail": f"CPU {cpu_percent:.1f}%"})

    mem_percent = _safe_float(resources.get("memory", {}).get("percent"))
    if mem_percent is not None and mem_percent >= 92:
        score -= 20
        issues.append({"key": "memory_high", "severity": "high", "detail": f"RAM {mem_percent:.1f}%"})
    elif mem_percent is not None and mem_percent >= 84:
        score -= 10
        issues.append({"key": "memory_warn", "severity": "medium", "detail": f"RAM {mem_percent:.1f}%"})

    root_usage = _safe_float(resources.get("storage", {}).get("/", {}).get("usage_percent"))
    if root_usage is not None and root_usage >= 95:
        score -= 20
        issues.append({"key": "disk_high", "severity": "high", "detail": f"Disk / {root_usage:.1f}%"})
    elif root_usage is not None and root_usage >= 88:
        score -= 10
        issues.append({"key": "disk_warn", "severity": "medium", "detail": f"Disk / {root_usage:.1f}%"})

    unavailable_ratio = _safe_float(sensors.get("availability_ratio"))
    if unavailable_ratio is not None:
        down_ratio = 1.0 - unavailable_ratio
        if down_ratio >= 0.25:
            score -= 20
            issues.append(
                {
                    "key": "sensor_offline_high",
                    "severity": "high",
                    "detail": f"{int(round(down_ratio * 100))}% Sensoren offline",
                }
            )
        elif down_ratio >= 0.1:
            score -= 10
            issues.append(
                {
                    "key": "sensor_offline_warn",
                    "severity": "medium",
                    "detail": f"{int(round(down_ratio * 100))}% Sensoren offline",
                }
            )

    missing_critical = services.get("missing_critical", [])
    if missing_critical:
        score -= min(30, 10 * len(missing_critical))
        issues.append(
            {
                "key": "critical_services_missing",
                "severity": "high",
                "detail": ", ".join(missing_critical),
            }
        )

    modules_total = int(modules.get("count", 0) or 0)
    modules_ready = int(modules.get("service_ready_count", 0) or 0)
    if modules_total > 0 and modules_ready < modules_total:
        not_ready = modules_total - modules_ready
        score -= min(20, not_ready * 2)
        issues.append(
            {
                "key": "module_connectivity_partial",
                "severity": "medium",
                "detail": f"{not_ready}/{modules_total} Module ohne Service-Backend",
            }
        )

    score = max(0, min(100, score))
    if score >= 85:
        status = "healthy"
    elif score >= 65:
        status = "degraded"
    else:
        status = "critical"

    return {
        "status": status,
        "score": score,
        "issue_count": len(issues),
        "issues": issues,
        "summary": (
            "System stabil"
            if status == "healthy"
            else "System eingeschraenkt"
            if status == "degraded"
            else "System kritisch"
        ),
    }


def _build_overview_payload(force: bool, sensor_limit: int) -> tuple[dict[str, Any], bool]:
    now = time.time()
    cached_payload = _OVERVIEW_CACHE.get("payload")
    cached_ts = float(_OVERVIEW_CACHE.get("timestamp", 0.0) or 0.0)
    if (
        not force
        and isinstance(cached_payload, dict)
        and (now - cached_ts) < _OVERVIEW_TTL_SECONDS
    ):
        out = dict(cached_payload)
        cache = dict(out.get("cache", {}))
        cache["served_from_cache"] = True
        cache["age_seconds"] = round(now - cached_ts, 3)
        out["cache"] = cache
        return out, True

    services = current_app.config.get("COPILOT_SERVICES", {})
    states = _fetch_home_assistant_states()
    sensors = _build_sensor_inventory(states, limit_items=sensor_limit)
    zones = _build_zone_summaries(states)
    neurons = _build_neuron_layer()
    resources = _build_resource_snapshot()
    service_info = _service_overview(services)
    module_info = _module_overview(services)
    overall = _overall_health_summary(resources, sensors, service_info, module_info)

    payload = {
        "ok": True,
        "time": _now_iso(),
        "uptime_seconds": int(time.time() - current_app.config.get("STARTUP_TIME", time.time())),
        "overall": overall,
        "resources": resources,
        "services": service_info,
        "modules": module_info,
        "neurons": neurons,
        "sensors": sensors,
        "zones": zones,
        "cache": {
            "ttl_seconds": int(_OVERVIEW_TTL_SECONDS),
            "served_from_cache": False,
            "age_seconds": 0.0,
        },
    }
    _OVERVIEW_CACHE["timestamp"] = now
    _OVERVIEW_CACHE["payload"] = payload
    return payload, False


@system_status_bp.route("/status", methods=["GET"])
@require_token
def get_status():
    """Compact status endpoint used by lightweight status checks."""
    overview, _ = _build_overview_payload(force=False, sensor_limit=120)
    return jsonify(
        {
            "ok": True,
            "time": overview["time"],
            "uptime_seconds": overview["uptime_seconds"],
            "overall": overview["overall"],
            "services": {
                row["service"]: row["available"] for row in overview["services"]["services"]
            },
        }
    )


@system_status_bp.route("/overview", methods=["GET"])
@require_token
def get_overview():
    """Detailed system overview for React dashboard and zone management UX."""
    force = _bool_arg(request.args.get("force"))
    try:
        sensor_limit = int(request.args.get("sensor_limit", "220"))
    except ValueError:
        sensor_limit = 220
    sensor_limit = max(20, min(sensor_limit, 800))
    payload, _ = _build_overview_payload(force=force, sensor_limit=sensor_limit)
    return jsonify(payload)


@system_status_bp.route("/cache/clear", methods=["POST"])
@require_token
def clear_overview_cache():
    """Invalidate system overview cache for immediate dashboard refresh."""
    _OVERVIEW_CACHE["timestamp"] = 0.0
    _OVERVIEW_CACHE["payload"] = None
    return jsonify({"ok": True, "cleared": True, "time": _now_iso()})


@system_status_bp.route("/modules", methods=["GET"])
@require_token
def list_modules():
    """List module states/connectivity details."""
    payload, _ = _build_overview_payload(force=_bool_arg(request.args.get("force")), sensor_limit=100)
    modules = payload.get("modules", {})
    return jsonify(
        {
            "ok": True,
            "count": modules.get("count", 0),
            "states": modules.get("states", {}),
            "modules": modules.get("modules", []),
        }
    )


@system_status_bp.route("/sensors", methods=["GET"])
@require_token
def list_sensors():
    """List managed PilotSuite sensors/entities with module + neuron mapping."""
    force = _bool_arg(request.args.get("force"))
    try:
        sensor_limit = int(request.args.get("limit", "320"))
    except ValueError:
        sensor_limit = 320
    sensor_limit = max(20, min(sensor_limit, 1000))
    payload, _ = _build_overview_payload(force=force, sensor_limit=sensor_limit)
    sensors = payload.get("sensors", {})
    return jsonify(
        {
            "ok": True,
            "time": payload.get("time"),
            "summary": {
                "total_entities": sensors.get("total_entities", 0),
                "sensor_count": sensors.get("sensor_count", 0),
                "available_entities": sensors.get("available_entities", 0),
                "unavailable_entities": sensors.get("unavailable_entities", 0),
                "availability_ratio": sensors.get("availability_ratio", 0),
                "target_94_reached": sensors.get("target_94_reached", False),
            },
            "by_domain": sensors.get("by_domain", {}),
            "by_module": sensors.get("by_module", []),
            "items": sensors.get("items", []),
            "items_truncated": sensors.get("items_truncated", False),
        }
    )


@system_status_bp.route("/zones/summary", methods=["GET"])
@require_token
def zone_summary():
    """Return zone-level availability + metric summary for Habitus page."""
    payload, _ = _build_overview_payload(force=_bool_arg(request.args.get("force")), sensor_limit=140)
    return jsonify(
        {
            "ok": True,
            "time": payload.get("time"),
            "count": len(payload.get("zones", [])),
            "zones": payload.get("zones", []),
        }
    )


@system_status_bp.route("/config", methods=["GET"])
@require_token
def get_config():
    """Get current configuration (safe fields only)."""
    services = current_app.config.get("COPILOT_SERVICES", {})
    config = services.get("config", {})
    safe_config = {
        "version": config.get("version"),
        "conversation_enabled": config.get("conversation_enabled"),
        "searxng_enabled": config.get("searxng_enabled"),
    }
    return jsonify({"ok": True, "config": safe_config})


# ── Version Check & Update ───────────────────────────────────────
_GITHUB_REPOS = {
    "core": "GreenhillEfka/pilotsuite-styx-core",
    "ha": "GreenhillEfka/pilotsuite-styx-ha",
}


def _get_current_version() -> str:
    """Read version from config.yaml."""
    import yaml  # noqa: PLC0415

    for path in ["/data/options.json", "config.yaml"]:
        try:
            if path.endswith(".json"):
                import json  # noqa: PLC0415

                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, dict) and data.get("version"):
                        return str(data["version"])
            else:
                with open(path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
                    if isinstance(data, dict) and data.get("version"):
                        return str(data["version"])
        except Exception:
            continue
    services = current_app.config.get("COPILOT_SERVICES", {})
    return str(services.get("config", {}).get("version", "unknown"))


def _fetch_latest_github_release(repo: str) -> dict | None:
    """Fetch latest release from GitHub API (best-effort, no auth required)."""
    import urllib.request  # noqa: PLC0415

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            import json  # noqa: PLC0415

            data = json.loads(resp.read().decode())
            return {
                "tag_name": data.get("tag_name", ""),
                "name": data.get("name", ""),
                "published_at": data.get("published_at", ""),
                "html_url": data.get("html_url", ""),
                "body": (data.get("body") or "")[:500],
            }
    except Exception as exc:
        logger.debug("GitHub release check failed for %s: %s", repo, exc)
        return None


@system_status_bp.route("/check-update", methods=["GET"])
@require_token
def check_update():
    """Check GitHub for latest release and compare with current version."""
    current = _get_current_version()
    core_release = _fetch_latest_github_release(_GITHUB_REPOS["core"])
    ha_release = _fetch_latest_github_release(_GITHUB_REPOS["ha"])

    latest_core = (core_release or {}).get("tag_name", "").lstrip("v") if core_release else None
    latest_ha = (ha_release or {}).get("tag_name", "").lstrip("v") if ha_release else None
    latest = latest_core or latest_ha or current

    return jsonify({
        "ok": True,
        "current_version": current,
        "latest_version": latest,
        "update_available": latest != current,
        "core_release": core_release,
        "ha_release": ha_release,
    })


@system_status_bp.route("/update", methods=["POST"])
@require_token
def trigger_update():
    """Trigger HA Supervisor add-on update (if running under Supervisor)."""
    import urllib.request  # noqa: PLC0415

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not supervisor_token:
        return jsonify({"ok": False, "error": "No SUPERVISOR_TOKEN — not running under HA Supervisor"}), 400

    slug = os.environ.get("HOSTNAME", "local_pilotsuite_styx_core")
    url = f"http://supervisor/addons/{slug}/update"
    try:
        req = urllib.request.Request(
            url,
            method="POST",
            headers={
                "Authorization": f"Bearer {supervisor_token}",
                "Content-Type": "application/json",
            },
            data=b"{}",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return jsonify({"ok": True, "status": resp.status, "message": "Update triggered"})
    except Exception as exc:
        logger.exception("Update trigger failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


@system_status_bp.route("/github-status", methods=["GET"])
@require_token
def github_status():
    """Check GitHub repo status and compare versions."""
    current = _get_current_version()
    core_release = _fetch_latest_github_release(_GITHUB_REPOS["core"])
    latest = (core_release or {}).get("tag_name", "").lstrip("v") if core_release else current

    return jsonify({
        "ok": True,
        "repo": _GITHUB_REPOS["core"],
        "current_version": current,
        "latest_version": latest,
        "up_to_date": current == latest,
        "release_notes": (core_release or {}).get("body", ""),
        "release_url": (core_release or {}).get("html_url", ""),
    })


@system_status_bp.route("/download-version", methods=["POST"])
@require_token
def download_version():
    """Download current version source from GitHub for self-repair reference."""
    import subprocess  # noqa: PLC0415

    current = _get_current_version()
    repo = _GITHUB_REPOS["core"]
    target_dir = "/data/repo_reference"

    try:
        os.makedirs(target_dir, exist_ok=True)
        tag = f"v{current}"
        tarball_url = f"https://github.com/{repo}/archive/refs/tags/{tag}.tar.gz"
        result = subprocess.run(
            ["wget", "-qO-", tarball_url],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0:
            tar_path = os.path.join(target_dir, f"{tag}.tar.gz")
            with open(tar_path, "wb") as fh:
                fh.write(result.stdout)
            return jsonify({"ok": True, "path": tar_path, "version": current})

        return jsonify({"ok": False, "error": "Download failed", "stderr": result.stderr.decode()[:200]}), 500
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
