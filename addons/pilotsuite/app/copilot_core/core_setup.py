"""
Core Setup - Service initialization and blueprint registration.

Optimized for performance with lazy loading support for heavy modules.
Startup time target: <2s (from ~5s)

Features:
- Lazy loading for Energy, ML, Calendar modules
- Configurable via lazy_load_enabled flag
- Performance metrics tracking
- Memory optimization: only load modules when needed
- Data-driven engine/blueprint registration to reduce boilerplate
"""

import importlib
import logging
import os
import threading
import time
from typing import Dict, Any, Optional
from flask import Flask

_LOGGER = logging.getLogger(__name__)


def _init_engine_group(
    services: dict,
    engine_defs: list[tuple[str, str, str]],
    group_name: str,
) -> None:
    """Initialize a group of engines from (service_key, module_path, class_name) tuples.

    Each engine is instantiated with no arguments. Failures are logged
    individually; the remaining engines continue to initialize.
    """
    ok_count = 0
    for service_key, module_path, class_name in engine_defs:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            services[service_key] = cls()
            ok_count += 1
        except Exception:
            _LOGGER.exception("Failed to init %s.%s", module_path, class_name)
    _LOGGER.info("%s initialized (%d/%d services)", group_name, ok_count, len(engine_defs))


def _wire_bus_events(services: dict) -> None:
    """Wire IntegrationBus event subscriptions between services.

    Each wiring is isolated — a failure in one does not affect the others.
    """
    bus = services.get("integration_bus")
    if not bus:
        return

    # 1) Anomaly Detection ← state.changed (with periodic detect + bus publish)
    #    Also publishes anomalies to brain graph if available.
    hub_anomaly = services.get("hub_anomaly")
    _brain_graph_svc = services.get("brain_graph_service")
    if hub_anomaly and hasattr(hub_anomaly, "ingest"):
        try:
            _anomaly_lock = threading.Lock()
            _anomaly_ingest_count = [0]
            _ANOMALY_DETECT_EVERY = 20   # run detect() every N ingestions
            # Deduplication: track recently published (entity_id, anomaly_type) to
            # avoid flooding the bus with the same anomaly every detect() cycle.
            _anomaly_recent: dict[str, float] = {}  # key → timestamp
            _ANOMALY_DEDUP_WINDOW = 600  # suppress duplicates for 10 minutes

            def _anomaly_from_event(event, _svc=hub_anomaly, _bus=bus, _bg=_brain_graph_svc):
                data = event.data if hasattr(event, "data") else {}
                entity_id = data.get("entity_id", "")
                value = data.get("value")
                if entity_id and value is not None:
                    try:
                        _svc.ingest(entity_id, float(value))
                    except (ValueError, TypeError):
                        return

                    should_detect = False
                    with _anomaly_lock:
                        _anomaly_ingest_count[0] += 1
                        if _anomaly_ingest_count[0] >= _ANOMALY_DETECT_EVERY:
                            _anomaly_ingest_count[0] = 0
                            should_detect = True

                    if should_detect:
                        try:
                            _svc.learn_patterns()
                            new_anomalies = _svc.detect()
                            now = time.time()
                            for anomaly in new_anomalies:
                                # Deduplicate: skip if same entity+type was published recently
                                dedup_key = f"{anomaly.entity_id}|{anomaly.anomaly_type}"
                                with _anomaly_lock:
                                    last_pub = _anomaly_recent.get(dedup_key, 0)
                                    if now - last_pub < _ANOMALY_DEDUP_WINDOW:
                                        continue
                                    _anomaly_recent[dedup_key] = now
                                    # Evict stale entries (keep dict bounded)
                                    if len(_anomaly_recent) > 200:
                                        cutoff = now - _ANOMALY_DEDUP_WINDOW
                                        _anomaly_recent.clear()
                                        # No need to rebuild — next cycle will repopulate

                                _bus.publish("anomaly.detected", {
                                    "anomaly_id": anomaly.anomaly_id,
                                    "entity_id": anomaly.entity_id,
                                    "anomaly_type": anomaly.anomaly_type,
                                    "severity": anomaly.severity,
                                    "score": anomaly.score,
                                    "detected_at": anomaly.detected_at.isoformat(),
                                    "value": anomaly.value,
                                    "expected_value": anomaly.expected_value,
                                    "deviation_pct": anomaly.deviation_pct,
                                    "description": anomaly.description_de,
                                })

                                # Publish anomaly to brain graph
                                if _bg and hasattr(_svc, "publish_to_brain_graph"):
                                    try:
                                        _svc.publish_to_brain_graph(anomaly, _bg)
                                    except Exception:
                                        _LOGGER.debug("Anomaly→BrainGraph publish failed", exc_info=True)
                        except Exception:
                            _LOGGER.debug("AnomalyDetection detect cycle failed", exc_info=True)

            bus.subscribe("state.changed", _anomaly_from_event)
            _LOGGER.info("AnomalyDetection wired to state.changed events (detect every %d ingestions)", _ANOMALY_DETECT_EVERY)
            if _brain_graph_svc:
                _LOGGER.info("AnomalyDetection→BrainGraph integration active")
        except Exception:
            _LOGGER.exception("Failed to wire AnomalyDetection")

    # 2) Predictive Maintenance ← device.metric
    hub_maintenance = services.get("hub_maintenance")
    if hub_maintenance and hasattr(hub_maintenance, "ingest_metric"):
        try:
            def _maintenance_from_event(event, _svc=hub_maintenance):
                data = event.data if hasattr(event, "data") else {}
                device_id = data.get("device_id", "")
                metric = data.get("metric", "")
                value = data.get("value")
                if device_id and metric and value is not None:
                    try:
                        _svc.ingest_metric(device_id, metric, float(value))
                    except (ValueError, TypeError):
                        pass

            bus.subscribe("device.metric", _maintenance_from_event)
            _LOGGER.info("PredictiveMaintenance wired to device.metric events")
        except Exception:
            _LOGGER.exception("Failed to wire PredictiveMaintenance")

    # 3) Scene Intelligence ← presence.changed
    hub_scenes = services.get("hub_scenes")
    if hub_scenes and hasattr(hub_scenes, "suggest_scenes"):
        try:
            def _scene_from_presence(event, _svc=hub_scenes):
                data = event.data if hasattr(event, "data") else {}
                zone_id = data.get("zone_id", "")
                if zone_id:
                    try:
                        from copilot_core.hub.scene_intelligence import SceneContext
                        from datetime import datetime, timezone
                        now = datetime.now(tz=timezone.utc)
                        ctx = SceneContext(
                            hour=now.hour,
                            is_home=data.get("is_home", True),
                            occupancy_count=data.get("occupancy_count", 1),
                            active_zone=zone_id,
                            is_weekend=now.weekday() >= 5,
                        )
                        _svc.suggest_scenes(ctx, limit=3)
                    except Exception:
                        _LOGGER.debug("SceneIntelligence suggest_scenes failed for zone %s", zone_id, exc_info=True)

            bus.subscribe("presence.changed", _scene_from_presence)
            _LOGGER.info("SceneIntelligence wired to presence.changed events")
        except Exception:
            _LOGGER.exception("Failed to wire SceneIntelligence")

    # 4) Notification Intelligence ← anomaly.detected
    hub_notifications = services.get("hub_notifications")
    if hub_notifications and hasattr(hub_notifications, "add_notification"):
        try:
            def _notify_on_anomaly(event, _svc=hub_notifications):
                data = event.data if hasattr(event, "data") else {}
                severity = data.get("severity", "info")
                if severity in ("warning", "critical"):
                    try:
                        _svc.add_notification(
                            title=f"Anomalie erkannt: {data.get('entity_id', 'unbekannt')}",
                            message=data.get("description", ""),
                            severity=severity,
                            category="anomaly",
                            source="anomaly_detection",
                        )
                    except Exception:
                        _LOGGER.debug("NotificationIntelligence add_notification failed", exc_info=True)

            bus.subscribe("anomaly.detected", _notify_on_anomaly)
            _LOGGER.info("NotificationIntelligence wired to anomaly.detected events")
        except Exception:
            _LOGGER.exception("Failed to wire NotificationIntelligence")

    # 5) Anomaly Detection → Webhook Push to HA
    pusher = services.get("webhook_pusher")
    if pusher and hub_anomaly:
        try:
            def _push_anomaly_to_ha(event, _pusher=pusher):
                data = event.data if hasattr(event, "data") else {}
                severity = data.get("severity", "info")
                if severity in ("warning", "critical"):
                    try:
                        _pusher.push_anomaly_detected(data)
                    except Exception:
                        _LOGGER.debug("Webhook push for anomaly failed", exc_info=True)

            bus.subscribe("anomaly.detected", _push_anomaly_to_ha)
            _LOGGER.info("WebhookPusher wired to anomaly.detected events")
        except Exception:
            _LOGGER.exception("Failed to wire anomaly → webhook push")

    # 6) Anomaly Detection → Proactive Engine (suggestions context)
    #    Only forward warning/critical — info-level anomalies are too noisy
    #    for user-facing suggestions.
    proactive = services.get("proactive_engine")
    if proactive and hasattr(proactive, "add_context"):
        try:
            def _anomaly_to_proactive(event, _svc=proactive):
                data = event.data if hasattr(event, "data") else {}
                severity = data.get("severity", "info")
                if severity not in ("warning", "critical"):
                    return
                try:
                    _svc.add_context("anomaly", {
                        "entity_id": data.get("entity_id"),
                        "severity": severity,
                        "type": data.get("anomaly_type"),
                        "score": data.get("score", 0),
                        "description": data.get("description", ""),
                    })
                except Exception:
                    _LOGGER.debug("ProactiveEngine add_context failed", exc_info=True)

            bus.subscribe("anomaly.detected", _anomaly_to_proactive)
            _LOGGER.info("ProactiveEngine wired to anomaly.detected events (warning/critical only)")
        except Exception:
            _LOGGER.exception("Failed to wire anomaly → proactive engine")

    # 7) Pattern Discovery → RAG Embedding
    # NOTE: Removed bus-based embedding here to avoid double-embedding.
    # HabitusMinerService._embed_rules_in_rag() handles embedding directly
    # after mining (with richer context like dt_sec).  It only embeds when
    # the embedding engine uses Ollama (semantic); hash-only is skipped.

    # 8) AutonomyExecutor ← mood.changed + presence.changed
    executor = services.get("autonomy_executor")
    if executor:
        try:
            bus.subscribe("mood.changed", executor.on_mood_changed)
            bus.subscribe("presence.changed", executor.on_presence_changed)
            _LOGGER.info("AutonomyExecutor wired to mood.changed + presence.changed")
        except Exception:
            _LOGGER.exception("Failed to wire AutonomyExecutor bus events")


def _wire_habitus_auto_mining(services: dict) -> None:
    """Inject HabitusMinerService into EventProcessor for auto-triggered mining.

    The EventProcessor itself handles buffering and trigger logic (every N
    events or M seconds, configurable via HABITUS_AUTO_MINE_EVENT_THRESHOLD
    and HABITUS_AUTO_MINE_INTERVAL_S env vars).  Mining runs in a background
    thread so it never blocks event processing.
    """
    try:
        from copilot_core.habitus_miner.service import HabitusMinerService
        from pathlib import Path

        event_processor = services.get("event_processor")
        if not event_processor:
            _LOGGER.warning("No EventProcessor available — skipping habitus auto-mining wiring")
            return

        # Resolve storage dir (same as lazy-init in api/v1/habitus.py)
        data_dir = services.get("config", {}).get("data_dir", "/data")
        storage_dir = Path(data_dir) / "habitus_miner"

        miner = HabitusMinerService(
            storage_dir=storage_dir,
            vector_store=services.get("vector_store"),
            embedding_engine=services.get("embedding_engine"),
            integration_bus=services.get("integration_bus"),
        )

        event_processor.set_habitus_miner(miner)
        _LOGGER.info("Habitus auto-mining wired into EventProcessor")
    except Exception:
        _LOGGER.exception("Failed to wire habitus auto-mining")



def _brain_graph_option(config: dict, nested_key: str, top_level_key: str, default: int) -> int:
    """Resolve a brain_graph config value — nested block takes precedence over top-level."""
    bg = config.get("brain_graph", {})
    if nested_key in bg:
        return _safe_int(bg[nested_key], default)
    if top_level_key in config:
        return _safe_int(config[top_level_key], default)
    return default


def _safe_int(value, default: int, minimum: int = 1, maximum: int = 100000) -> int:
    """Parse an int config value with bounds checking."""
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float, minimum: float = 0.0, maximum: float = 1e6) -> float:
    """Parse a float config value with bounds checking."""
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        return default


async def init_services(hass=None, config: dict = None):
    """
    Initialize all core services with lazy loading support.

    Each service block is wrapped in try/except so a single failure does not
    prevent the remaining services from starting.
    
    Args:
        hass: Home Assistant instance (optional)
        config: Configuration dictionary (optional)
    
    Returns:
        Dictionary of initialized services
    """
    config = config or {}
    start_time = time.perf_counter()
    
    # Initialize connection pooling FIRST (before any service that makes HTTP calls)
    try:
        from copilot_core.connection_pool import get_pool_manager
        pool = await get_pool_manager()
        _LOGGER.info(
            "Connection pooling initialized (max_connections=%d, timeout=%ds)",
            pool.max_connections,
            pool.timeout,
        )
    except Exception:
        _LOGGER.exception("Failed to init ConnectionPoolManager")
    
    # Check if lazy loading is enabled
    lazy_load_enabled = config.get("lazy_load_enabled", True)
    
    if lazy_load_enabled:
        _LOGGER.info("Lazy loading ENABLED - deferring heavy module initialization")
        from copilot_core.utils.lazy_loader import LazyLoader
        LazyLoader.enable()
    else:
        _LOGGER.info("Lazy loading DISABLED - loading all modules immediately")
        from copilot_core.utils.lazy_loader import LazyLoader
        LazyLoader.disable()
    
    services: dict = {
        "config": config,
        "lazy_load_enabled": lazy_load_enabled,
        "startup_time_ms": 0.0,
        # Core services
        "system_health_service": None,
        "unifi_service": None,
        "energy_service": None,
        "brain_graph_service": None,
        "graph_renderer": None,
        "candidate_store": None,
        "habitus_service": None,
        "chat_handler": None,
        "mood_service": None,
        "event_processor": None,
        "tag_registry": None,
        "tag_zone_integration": None,
        "webhook_pusher": None,
        "household_profile": None,
        "neuron_manager": None,
        "conversation_memory": None,
        "telegram_bot": None,
        "module_registry": None,
        "automation_creator": None,
        "media_zone_manager": None,
        "sonos_client": None,
        "musikwolke_bridge": None,
        "proactive_engine": None,
        "web_search_service": None,
        "waste_service": None,
        "birthday_service": None,
        "vector_store": None,
        "embedding_engine": None,
        # PilotSuite Hub engines (v7.6.0)
        "hub_dashboard": None,
        "hub_plugin_manager": None,
        "hub_multi_home": None,
        "hub_maintenance": None,
        "hub_anomaly": None,
        "hub_zones": None,
        "hub_light": None,
        "hub_modes": None,
        "hub_media": None,
        "hub_energy": None,
        "hub_templates": None,
        "hub_scenes": None,
        "hub_presence": None,
        "hub_notifications": None,
        "hub_integration": None,
        "hub_brain_arch": None,
        "hub_brain_activity": None,
        # PilotSuite Module (v1.0.0)
        "hub_licht": None,
        "hub_helligkeit": None,
        "hub_heiz": None,
        "hub_bewegung": None,
        "hub_praesenz": None,
        # Network + HA Integration Modules
        "hub_zwave": None,
        "hub_zigbee": None,
        "hub_thread": None,
        "ha_module_engine": None,
        "module_router": None,
        # Weather service (for energy forecast engines)
        "weather_service": None,
        # Wecker (Smart Alarm) service
        "wecker": None,
        # Multi-user conflict resolution
        "conflict_resolver": None,
        # ML Pipeline (inference + training)
        "inference_engine": None,
        "training_pipeline": None,
        # ML Habit Prediction + Multi-User Learning
        "habit_predictor": None,
        "multi_user_learner": None,
        # Styx Character (personality presets)
        "character_service": None,
        # Styx Action Attribution + User Hints NLP
        "action_attribution": None,
        "user_hints": None,
    }

    # Initialize system health service (requires hass)
    try:
        if hass:
            services["system_health_service"] = SystemHealthService(hass)
    except Exception:
        _LOGGER.exception("Failed to init SystemHealthService")

    # Initialize UniFi service (requires hass)
    try:
        if hass:
            services["unifi_service"] = UniFiService(hass)
    except Exception:
        _LOGGER.exception("Failed to init UniFiService")

    # Initialize energy service with lazy loading
    try:
        if hass:
            if lazy_load_enabled:
                # Use lazy loader - defer initialization
                from copilot_core.utils.lazy_loader import energy_service_loader
                services["energy_service"] = energy_service_loader
                _LOGGER.debug("EnergyService deferred via lazy loader")
            else:
                from copilot_core.energy.service import EnergyService
                services["energy_service"] = EnergyService(hass)
    except Exception:
        _LOGGER.exception("Failed to init EnergyService")

    # Initialize Weather Service (provides data to energy forecast engines)
    try:
        from copilot_core.api.v1.weather import WeatherService, init_weather_api
        location = config.get("location", {}) if config else {}
        lat = _safe_float(location.get("latitude", 52.5), 52.5, -90.0, 90.0)
        lon = _safe_float(location.get("longitude", 13.4), 13.4, -180.0, 180.0)
        weather_svc = WeatherService(lat=lat, lon=lon)
        services["weather_service"] = weather_svc
        init_weather_api(lat=lat, lon=lon)
        _LOGGER.info("WeatherService initialized (lat=%.2f, lon=%.2f)", lat, lon)
    except Exception:
        _LOGGER.exception("Failed to init WeatherService")

    # Parse Brain Graph configuration with validation
    try:
        bg_config = config.get("brain_graph", {}) if config else {}
        brain_graph_service = BrainGraphService(
            store=GraphStore(
                max_nodes=_safe_int(bg_config.get("max_nodes", 500), 500, 100, 5000),
                max_edges=_safe_int(bg_config.get("max_edges", 1500), 1500, 100, 15000),
                node_min_score=_safe_float(bg_config.get("node_min_score", 0.1), 0.1, 0.0, 1.0),
                edge_min_weight=_safe_float(bg_config.get("edge_min_weight", 0.1), 0.1, 0.0, 1.0),
            ),
            node_half_life_hours=_safe_float(bg_config.get("node_half_life_hours", 24.0), 24.0, 0.1, 8760.0),
            edge_half_life_hours=_safe_float(bg_config.get("edge_half_life_hours", 12.0), 12.0, 0.1, 8760.0),
            prune_interval_minutes=_safe_int(bg_config.get("prune_interval_minutes", 60), 60, 1, 1440),
        )
        brain_graph_service.start_scheduled_pruning()
        services["brain_graph_service"] = brain_graph_service
        services["graph_renderer"] = GraphRenderer()

        # Wire properly initialized BrainGraphService into the API singleton (P3-003 fix)
        try:
            from copilot_core.brain_graph.api import init_brain_graph_api
            init_brain_graph_api(services["brain_graph_service"], services["graph_renderer"])
        except Exception:
            _LOGGER.warning("Failed to wire brain_graph_api: %s", e)

    except Exception:
        _LOGGER.exception("Failed to init BrainGraphService")

    # Initialize candidates store
    try:
        candidate_store = CandidateStore()
        services["candidate_store"] = candidate_store
    except Exception:
        _LOGGER.exception("Failed to init CandidateStore")

    # Initialize habitus service
    try:
        if services["brain_graph_service"] and services["candidate_store"]:
            habitus_service = HabitusService(services["brain_graph_service"], services["candidate_store"])
            services["habitus_service"] = habitus_service
    except Exception:
        _LOGGER.exception("Failed to init HabitusService")

    # Initialize ChatHandler for Styx Chat API
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        chat_handler = ChatHandler()
        services["chat_handler"] = chat_handler
        _LOGGER.info("ChatHandler initialized (Styx Chat)")
    except Exception:
        _LOGGER.exception("Failed to init ChatHandler")

    # Initialize mood service
    try:
        mood_service = MoodService()
        services["mood_service"] = mood_service
    except Exception:
        _LOGGER.exception("Failed to init MoodService")

    # Initialize event processor: EventStore → BrainGraph pipeline
    try:
        if services["brain_graph_service"]:
            event_processor = EventProcessor(brain_graph_service=services["brain_graph_service"])
            services["event_processor"] = event_processor
            set_post_ingest_callback(event_processor.process_events)
    except Exception:
        _LOGGER.exception("Failed to init EventProcessor")

    # Wire mood service into event processor (v3.1.0)
    try:
        event_processor = services.get("event_processor")
        mood_service = services.get("mood_service")
        if event_processor and mood_service:
            def _mood_event_processor(event: dict) -> None:
                """Derive mood updates from HA events (media_player, person)."""
                attrs = event.get("attributes", {})
                domain = attrs.get("domain", "")
                entity_id = event.get("entity_id", "")
                new_state = attrs.get("new_state", "")
                zone_ids = attrs.get("zone_ids", [])

                if domain == "media_player" and zone_ids:
                    is_playing = new_state in ("playing", "on")
                    for zone_id in zone_ids:
                        mood_service.update_from_media_context({
                            "music_active": is_playing,
                            "tv_active": False,
                            "primary_player": {
                                "entity_id": entity_id,
                                "state": new_state,
                                "media_title": "",
                                "area": zone_id,
                            },
                        })
            event_processor.add_processor(_mood_event_processor)
            _LOGGER.info("Mood event processor wired into EventProcessor pipeline")
    except Exception:
        _LOGGER.exception("Failed to wire mood event processor")

    # Initialize Tag System v0.2 (Decision Matrix 2026-02-14)
    try:
        services["tag_registry"] = TagRegistry()
    except Exception:
        _LOGGER.exception("Failed to init TagRegistry")

    # Wire TagZoneIntegration: bridges tags → HabitusZones (auto-zone from place tags)
    try:
        tag_registry = services.get("tag_registry")
        if tag_registry:
            from copilot_core.tagging.zone_integration import create_tag_zone_integration
            tag_zone_integration = create_tag_zone_integration(tag_registry)
            services["tag_zone_integration"] = tag_zone_integration
            _LOGGER.info("TagZoneIntegration wired to TagRegistry")
        else:
            services["tag_zone_integration"] = None
    except Exception:
        _LOGGER.exception("Failed to init TagZoneIntegration")
        services["tag_zone_integration"] = None

    # Initialize Webhook Pusher
    try:
        webhook_url = config.get("webhook_url", "") if config else ""
        webhook_token = config.get("webhook_token", "") if config else ""
        # Signing key rotation: legacy `webhook_signing_secret` stays supported.
        webhook_signing_secret = config.get("webhook_signing_secret", "") if config else ""
        webhook_signing_secret_primary = (
            config.get("webhook_signing_secret_primary", "") if config else ""
        )
        webhook_signing_secret_secondary = (
            config.get("webhook_signing_secret_secondary", "") if config else ""
        )
        webhook_signing_timestamp_ttl_seconds = _safe_int(
            config.get("webhook_signing_timestamp_ttl_seconds", 300) if config else 300,
            default=300,
            minimum=1,
            maximum=60 * 60 * 24,
        )

        if webhook_url and not (webhook_signing_secret or webhook_signing_secret_primary):
            _LOGGER.warning(
                "Webhook signing is not configured (webhook_signing_secret_primary is empty) — "
                "outgoing webhooks will not be signed. Set a signing secret for integrity protection."
            )

        # Optional per-destination caps (config first, then env fallback)
        dest_max_conc_value = config.get("webhook_destination_max_concurrency") if config else None
        if dest_max_conc_value is None:
            dest_max_conc_value = os.environ.get("PILOTSUITE_WEBHOOK_DESTINATION_MAX_CONCURRENCY")
        destination_max_concurrency: Optional[int] = 5
        if dest_max_conc_value is not None:
            destination_max_concurrency = _safe_int(
                dest_max_conc_value,
                default=5,
                minimum=1,
                maximum=1000,
            )

        dest_rate_per_sec_value = config.get("webhook_destination_rate_limit_per_second") if config else None
        if dest_rate_per_sec_value is None:
            dest_rate_per_sec_value = os.environ.get("PILOTSUITE_WEBHOOK_DESTINATION_RATE_LIMIT_PER_SECOND")
        destination_rate_limit_per_second: Optional[float] = 10.0
        if dest_rate_per_sec_value is not None:
            destination_rate_limit_per_second = _safe_float(
                dest_rate_per_sec_value,
                default=10.0,
                minimum=0.01,
                maximum=1e6,
            )

        dest_rate_burst_value = config.get("webhook_destination_rate_limit_burst") if config else None
        if dest_rate_burst_value is None:
            dest_rate_burst_value = os.environ.get("PILOTSUITE_WEBHOOK_DESTINATION_RATE_LIMIT_BURST")
        destination_rate_limit_burst = 5
        if dest_rate_burst_value is not None:
            destination_rate_limit_burst = _safe_int(
                dest_rate_burst_value,
                default=5,
                minimum=1,
                maximum=100000,
            )

        services["webhook_pusher"] = WebhookPusher(
            webhook_url,
            webhook_token,
            webhook_signing_secret=webhook_signing_secret,
            webhook_signing_secret_primary=webhook_signing_secret_primary,
            webhook_signing_secret_secondary=webhook_signing_secret_secondary,
            webhook_signing_timestamp_ttl_seconds=webhook_signing_timestamp_ttl_seconds,
            destination_max_concurrency=destination_max_concurrency,
            destination_rate_limit_per_second=destination_rate_limit_per_second,
            destination_rate_limit_burst=destination_rate_limit_burst,
        )
    except Exception:
        _LOGGER.exception("Failed to init WebhookPusher")

    # Initialize Household Profile
    try:
        household_config = config.get("household", {}) if config else {}
        services["household_profile"] = HouseholdProfile.from_config(household_config)
    except Exception:
        _LOGGER.exception("Failed to init HouseholdProfile")

    # NeuronManager initialization
    try:
        neuron_config = config.get("neurons", {}) if config else {}
        neuron_manager = NeuronManager()
        if services["household_profile"]:
            neuron_manager.set_household(services["household_profile"])
        neuron_manager.configure_from_ha({}, neuron_config)
        webhook_pusher = services.get("webhook_pusher")
        if webhook_pusher and webhook_pusher.enabled:
            def _enriched_mood_push(mood, conf, _pusher=webhook_pusher, _mgr=neuron_manager, _svcs=services):
                """Push mood with zone data, top neurons, and mood dimensions."""
                try:
                    # Per-zone mood snapshots
                    zone_moods = None
                    mood_svc = _svcs.get("mood_service")
                    if mood_svc and hasattr(mood_svc, "get_all_zone_moods"):
                        try:
                            raw = mood_svc.get_all_zone_moods()
                            zone_moods = {
                                zid: {"comfort": round(s.comfort, 3),
                                      "joy": round(s.joy, 3),
                                      "frugality": round(s.frugality, 3)}
                                for zid, s in raw.items()
                            } if raw else None
                        except Exception:
                            pass

                    # Top 3 most active neurons
                    top_neurons = None
                    try:
                        last = _mgr.get_last_result()
                        if last and last.neuron_states:
                            scored = []
                            for nid, ns in last.neuron_states.items():
                                val = ns.get("value", 0.0) if isinstance(ns, dict) else 0.0
                                layer = nid.split(".")[0] if "." in nid else "unknown"
                                scored.append({"id": nid, "layer": layer, "value": round(val, 3)})
                            scored.sort(key=lambda x: x["value"], reverse=True)
                            top_neurons = scored[:3]
                    except Exception:
                        pass

                    # Mood dimensions (average across zones)
                    mood_dimensions = None
                    if zone_moods:
                        try:
                            n = len(zone_moods)
                            mood_dimensions = {
                                "comfort": sum(z["comfort"] for z in zone_moods.values()) / n,
                                "joy": sum(z["joy"] for z in zone_moods.values()) / n,
                                "frugality": sum(z["frugality"] for z in zone_moods.values()) / n,
                            }
                        except Exception:
                            pass

                    _pusher.push_mood_changed(
                        mood, conf,
                        zone_moods=zone_moods,
                        top_neurons=top_neurons,
                        mood_dimensions=mood_dimensions,
                    )
                except Exception:
                    _LOGGER.debug("Enriched mood push failed, falling back to basic", exc_info=True)
                    _pusher.push_mood_changed(mood, conf)

            neuron_manager.on_mood_change(_enriched_mood_push)
            neuron_manager.on_suggestion(
                lambda suggestion: webhook_pusher.push_suggestion(suggestion)
            )
        services["neuron_manager"] = neuron_manager
    except Exception:
        _LOGGER.exception("Failed to init NeuronManager")

    # Initialize Conversation Memory (lifelong learning)
    try:
        from copilot_core.conversation_memory import ConversationMemory
        services["conversation_memory"] = ConversationMemory()
        _LOGGER.info("ConversationMemory initialized (lifelong learning active)")
    except Exception:
        _LOGGER.exception("Failed to init ConversationMemory")

    # Initialize Vector Store + Embedding Engine (RAG pipeline, v3.5.0)
    try:
        from copilot_core.vector_store import get_vector_store, get_embedding_engine
        embedding_engine = get_embedding_engine()
        vector_store = get_vector_store()
        vector_store.set_embedding_engine(embedding_engine)
        services["vector_store"] = vector_store
        services["embedding_engine"] = embedding_engine
        _LOGGER.info("VectorStore + EmbeddingEngine initialized (RAG pipeline active)")
    except Exception:
        _LOGGER.exception("Failed to init VectorStore / EmbeddingEngine")

    # Initialize Conflict Resolver (wired to UserPreferenceStore)
    try:
        from copilot_core.storage.conflict_resolution import ConflictResolver
        from copilot_core.storage.user_preferences import get_user_preference_store
        services["conflict_resolver"] = ConflictResolver(
            user_preference_store=get_user_preference_store(),
        )
        _LOGGER.info("ConflictResolver initialized")
    except Exception:
        _LOGGER.exception("Failed to init ConflictResolver")

    # Initialize ML Pipeline (Inference + Training)
    try:
        from copilot_core.ml.inference import InferenceEngine
        from copilot_core.ml.training import TrainingPipeline
        services["inference_engine"] = InferenceEngine()
        services["training_pipeline"] = TrainingPipeline()
        _LOGGER.info("ML Pipeline initialized (InferenceEngine + TrainingPipeline)")
    except Exception:
        _LOGGER.exception("Failed to init ML Pipeline")

    # Initialize Habit Predictor + Multi-User Learner
    try:
        from copilot_core.ml.habit_predictor import HabitPredictor
        from copilot_core.ml.multi_user_learner import MultiUserLearner
        services["habit_predictor"] = HabitPredictor()
        services["multi_user_learner"] = MultiUserLearner()
        _LOGGER.info("HabitPredictor + MultiUserLearner initialized")
    except Exception:
        _LOGGER.exception("Failed to init HabitPredictor / MultiUserLearner")

    # Initialize Styx Character Service
    try:
        from copilot_core.styx.character_service import CharacterService
        services["character_service"] = CharacterService()
        _LOGGER.info("CharacterService initialized")
    except Exception:
        _LOGGER.exception("Failed to init CharacterService")

    # Initialize Styx Action Attribution + User Hints NLP
    try:
        from copilot_core.styx.action_attribution import ActionAttributionEngine
        from copilot_core.styx.user_hints import UserHintsEngine
        services["action_attribution"] = ActionAttributionEngine()
        services["user_hints"] = UserHintsEngine()
        _LOGGER.info("ActionAttributionEngine + UserHintsEngine initialized")
    except Exception:
        _LOGGER.exception("Failed to init ActionAttribution / UserHints")

    # Initialize Telegram Bot with lazy loading
    try:
        telegram_config = config.get("telegram", {}) if config else {}
        if telegram_config.get("enabled", False):
            if lazy_load_enabled:
                from copilot_core.utils.lazy_loader import create_lazy_class
                telegram_bot_loader = create_lazy_class(
                    "telegram_bot",
                    "copilot_core.telegram",
                    "TelegramBot",
                    "Telegram bot integration"
                )
                services["telegram_bot"] = telegram_bot_loader
                _LOGGER.debug("TelegramBot deferred via lazy loader")
            else:
                from copilot_core.telegram import TelegramBot
                services["telegram_bot"] = TelegramBot(telegram_config)
                _LOGGER.info("TelegramBot initialized (eager)")
    except Exception:
        _LOGGER.exception("Failed to init TelegramBot")

    # Initialize Module Registry
    try:
        services["module_registry"] = ModuleRegistry()
    except Exception:
        _LOGGER.exception("Failed to init ModuleRegistry")

    # Initialize Integration Bus and wire to existing services
    try:
        from copilot_core.integration.bus import IntegrationBus
        from copilot_core.integration.feedback import FeedbackLoop
        bus = IntegrationBus.get_instance()
        services["integration_bus"] = bus

        # Wire bus to NeuronManager
        if services.get("neuron_manager"):
            services["neuron_manager"].set_bus(bus)

        # Wire bus to ModuleRegistry
        if services.get("module_registry"):
            services["module_registry"].set_bus(bus)

        # Initialize feedback loop (BrainGraph weight adjustments)
        if services.get("brain_graph_service"):
            feedback_loop = FeedbackLoop(services["brain_graph_service"], bus)
            services["feedback_loop"] = feedback_loop
        else:
            services["feedback_loop"] = None

        # Initialize integration API
        from copilot_core.integration.api import init_integration_api
        init_integration_api(bus, services.get("feedback_loop"))

        _LOGGER.info("IntegrationBus initialized and wired to services")
    except Exception:
        _LOGGER.exception("Failed to init IntegrationBus")

    # Initialize Neuron Layers Visualization API
    try:
        from copilot_core.api.v1.neuron_layers import init_neuron_layers_api
        if services.get("neuron_manager"):
            init_neuron_layers_api(
                services["neuron_manager"],
                services.get("integration_bus"),
            )
            _LOGGER.info("Neuron Layers Visualization API initialized")
    except Exception:
        _LOGGER.exception("Failed to init Neuron Layers API")

    # Initialize Hebbian Learning engine
    try:
        from copilot_core.neurons.learning import HebbianLearning
        from copilot_core.api.v1.neuron_layers import SYNAPSE_TOPOLOGY
        hebbian = HebbianLearning(
            topology=SYNAPSE_TOPOLOGY,
            persist_path="/data/synapse_weights.json",
        )
        services["hebbian_learning"] = hebbian

        # Wire learning to bus: update weights on each evaluation
        bus = services.get("integration_bus")
        if bus:
            def _on_eval_for_learning(event):
                values = {}
                for key in ("context_values", "state_values", "mood_values"):
                    prefix = key.split("_")[0]
                    for name, val in event.data.get(key, {}).items():
                        values[f"{prefix}.{name}"] = val
                hebbian.update_weights(values)

            bus.subscribe("neuron.evaluated", _on_eval_for_learning)

        _LOGGER.info("HebbianLearning initialized (%d synapses)", len(SYNAPSE_TOPOLOGY))
    except Exception:
        _LOGGER.exception("Failed to init HebbianLearning")

    # Initialize Cross-Module Analyzer
    try:
        from copilot_core.integration.cross_module import CrossModuleAnalyzer
        bus = services.get("integration_bus")
        if bus:
            analyzer = CrossModuleAnalyzer(bus)
            services["cross_module_analyzer"] = analyzer
            _LOGGER.info("CrossModuleAnalyzer initialized")
    except Exception:
        _LOGGER.exception("Failed to init CrossModuleAnalyzer")

    # Initialize Module Health Dashboard API
    try:
        from copilot_core.api.v1.module_health import init_module_health_api
        init_module_health_api(
            module_registry=services.get("module_registry"),
            integration_bus=services.get("integration_bus"),
            hebbian_learning=services.get("hebbian_learning"),
            cross_module_analyzer=services.get("cross_module_analyzer"),
            feedback_loop=services.get("feedback_loop"),
        )
        _LOGGER.info("Module Health Dashboard API initialized")
    except Exception:
        _LOGGER.exception("Failed to init Module Health API")

    # Initialize Automation Creator
    try:
        services["automation_creator"] = AutomationCreator()
    except Exception:
        _LOGGER.exception("Failed to init AutomationCreator")

    # Initialize Media Zone Manager
    try:
        services["media_zone_manager"] = MediaZoneManager()
    except Exception:
        _LOGGER.exception("Failed to init MediaZoneManager")

    # Initialize Sonos Client (jishi/node-sonos-http-api)
    try:
        sonos_host = config.get("sonos_api_host", "localhost")
        sonos_port = int(config.get("sonos_api_port", 5005))
        services["sonos_client"] = SonosCloudClient(
            host=sonos_host, port=sonos_port,
        )
        _LOGGER.info("SonosCloudClient initialized @ %s:%d", sonos_host, sonos_port)
    except Exception:
        _LOGGER.exception("Failed to init SonosCloudClient")

    # Initialize Proactive Engine with lazy loading
    try:
        if lazy_load_enabled:
            from copilot_core.utils.lazy_loader import proactive_engine_loader
            services["proactive_engine"] = proactive_engine_loader
            _LOGGER.debug("ProactiveContextEngine deferred via lazy loader")
        else:
            from copilot_core.proactive_context import ProactiveContextEngine
            services["proactive_engine"] = ProactiveContextEngine()
            _LOGGER.info("ProactiveContextEngine initialized (eager)")
        # Wire proactive engine into NeuronManager for mood-triggered suggestions
        engine = services.get("proactive_engine")
        neuron_mgr = services.get("neuron_manager")
        if engine and neuron_mgr and not lazy_load_enabled:
            neuron_mgr.set_proactive_engine(engine)
            _LOGGER.info("ProactiveContextEngine wired to NeuronManager (mood triggers)")
    except Exception:
        _LOGGER.exception("Failed to init ProactiveContextEngine")

    # Initialize Web Search Service with lazy loading
    try:
        if lazy_load_enabled:
            from copilot_core.utils.lazy_loader import web_search_loader
            services["web_search_service"] = web_search_loader
            _LOGGER.debug("WebSearchService deferred via lazy loader")
        else:
            from copilot_core.web_search import WebSearchService
            services["web_search_service"] = WebSearchService()
            _LOGGER.info("WebSearchService initialized (eager)")
    except Exception:
        _LOGGER.exception("Failed to init WebSearchService")

    # Initialize Waste Service
    try:
        waste_config = config.get("waste", {}) if config else {}
        services["waste_service"] = WasteCollectionService()
    except Exception:
        _LOGGER.exception("Failed to init WasteCollectionService")

    # Initialize Birthday Service
    try:
        birthday_config = config.get("birthdays", {}) if config else {}
        services["birthday_service"] = BirthdayService()
    except Exception:
        _LOGGER.exception("Failed to init BirthdayService")

    # Initialize PilotSuite Hub engines (data-driven)
    _HUB_ENGINES = [
        ("hub_dashboard",       "copilot_core.hub.dashboard",                "DashboardHub"),
        ("hub_plugin_manager",  "copilot_core.hub.plugin_manager",           "PluginManager"),
        ("hub_multi_home",      "copilot_core.hub.multi_home",               "MultiHomeManager"),
        ("hub_maintenance",     "copilot_core.hub.predictive_maintenance",   "PredictiveMaintenanceEngine"),
        ("hub_anomaly",         "copilot_core.hub.anomaly_detection",        "AnomalyDetectionEngine"),
        ("hub_zones",           "copilot_core.hub.habitus_zones",            "HabitusZoneEngine"),
        ("hub_light",           "copilot_core.hub.light_intelligence",       "LightIntelligenceEngine"),
        ("hub_modes",           "copilot_core.hub.zone_modes",               "ZoneModeEngine"),
        ("hub_media",           "copilot_core.hub.media_follow",             "MediaFollowEngine"),
        ("hub_energy",          "copilot_core.hub.energy_advisor",           "EnergyAdvisorEngine"),
        ("hub_templates",       "copilot_core.hub.automation_templates",     "AutomationTemplateEngine"),
        ("hub_scenes",          "copilot_core.hub.scene_intelligence",       "SceneIntelligenceEngine"),
        ("hub_presence",        "copilot_core.hub.presence_intelligence",    "PresenceIntelligenceEngine"),
        ("hub_notifications",   "copilot_core.hub.notification_intelligence","NotificationIntelligenceEngine"),
        ("hub_integration",     "copilot_core.hub.system_integration",       "SystemIntegrationHub"),
        ("hub_brain_arch",      "copilot_core.hub.brain_architecture",       "BrainArchitectureEngine"),
        ("hub_brain_activity",  "copilot_core.hub.brain_activity",           "BrainActivityEngine"),
    ]
    _init_engine_group(services, _HUB_ENGINES, "Hub engines")

    # Initialize Hub API with engines
    try:
        from copilot_core.hub.api import init_hub_api
        init_hub_api(
            dashboard=services["hub_dashboard"],
            plugin_manager=services["hub_plugin_manager"],
            multi_home=services["hub_multi_home"],
            maintenance_engine=services["hub_maintenance"],
            anomaly_engine=services["hub_anomaly"],
            zone_engine=services["hub_zones"],
            light_engine=services["hub_light"],
            mode_engine=services["hub_modes"],
            media_engine=services["hub_media"],
            energy_advisor=services["hub_energy"],
            template_engine=services["hub_templates"],
            scene_engine=services["hub_scenes"],
            presence_engine=services["hub_presence"],
            notification_engine=services["hub_notifications"],
            integration_hub=services["hub_integration"],
            brain_architecture=services["hub_brain_arch"],
            brain_activity=services["hub_brain_activity"],
        )
    except Exception:
        _LOGGER.exception("Failed to init Hub API")

    # Initialize PilotSuite Module engines (data-driven)
    _MODULE_ENGINES = [
        ("hub_licht",       "copilot_core.hub.licht_module",       "LichtModuleEngine"),
        ("hub_helligkeit",  "copilot_core.hub.helligkeit_module",  "HelligkeitModuleEngine"),
        ("hub_heiz",        "copilot_core.hub.heiz_module",        "HeizModuleEngine"),
        ("hub_bewegung",    "copilot_core.hub.bewegung_module",    "BewegungModuleEngine"),
        ("hub_praesenz",    "copilot_core.hub.praesenz_module",    "PraesenzModuleEngine"),
    ]
    _init_engine_group(services, _MODULE_ENGINES, "PilotSuite Module engines")

    # Initialize Network + HA Integration Module engines (data-driven)
    _NETWORK_ENGINES = [
        ("hub_zwave",       "copilot_core.hub.zwave_module",         "ZWaveModuleEngine"),
        ("hub_zigbee",      "copilot_core.hub.zigbee_module",        "ZigbeeModuleEngine"),
        ("hub_thread",      "copilot_core.hub.thread_module",        "ThreadModuleEngine"),
        ("ha_module_engine","copilot_core.hub.homeassistant_module",  "HomeAssistantModuleEngine"),
    ]
    _init_engine_group(services, _NETWORK_ENGINES, "Network + HA Module engines")

    # Initialize ModuleRouter — routes HA states to network modules
    try:
        from copilot_core.hub.module_router import ModuleRouter
        ha_client = services.get("ha_client")
        module_router = ModuleRouter(
            hub_zwave=services.get("hub_zwave"),
            hub_zigbee=services.get("hub_zigbee"),
            hub_thread=services.get("hub_thread"),
            ha_module_engine=services.get("ha_module_engine"),
            ha_client=ha_client,
        )
        services["module_router"] = module_router
        _LOGGER.info("ModuleRouter initialized (HA client: %s)", "yes" if ha_client else "no")

        # Wire ModuleRouter into EventProcessor for incremental state updates
        event_processor = services.get("event_processor")
        if event_processor and hasattr(event_processor, "add_processor"):
            event_processor.add_processor(module_router.ingest_event)
            _LOGGER.info("ModuleRouter wired to EventProcessor (incremental updates)")
    except Exception:
        _LOGGER.exception("Failed to init ModuleRouter")

    try:
        from copilot_core.api.v1.module_endpoints import init_module_endpoints
        init_module_endpoints(
            licht=services["hub_licht"],
            helligkeit=services["hub_helligkeit"],
            heiz=services["hub_heiz"],
            bewegung=services["hub_bewegung"],
            praesenz=services["hub_praesenz"],
        )
    except Exception:
        _LOGGER.exception("Failed to init PilotSuite Module endpoints")

    # Wire WebhookPusher module_data push via IntegrationBus
    try:
        webhook_pusher = services.get("webhook_pusher")
        bus = services.get("integration_bus")
        if webhook_pusher and webhook_pusher.enabled and bus:
            def _push_module_data_on_eval(event):
                """Push module summaries to HA after neuron evaluation."""
                modules = {}
                for name in ("hub_licht", "hub_helligkeit", "hub_heiz", "hub_bewegung", "hub_praesenz",
                             "hub_zwave", "hub_zigbee", "hub_thread"):
                    engine = services.get(name)
                    if engine and hasattr(engine, "get_summary"):
                        try:
                            modules[name.replace("hub_", "")] = engine.get_summary()
                        except Exception:
                            pass
                if modules:
                    webhook_pusher.push_module_data(modules)

            bus.subscribe("neuron.evaluated", _push_module_data_on_eval)
            _LOGGER.info("WebhookPusher module_data push wired to neuron.evaluated event")
    except Exception:
        _LOGGER.exception("Failed to wire WebhookPusher module_data push")

    # Wire WebhookPusher neuron_fired push via IntegrationBus
    try:
        webhook_pusher = services.get("webhook_pusher")
        bus = services.get("integration_bus")
        neuron_mgr = services.get("neuron_manager")
        if webhook_pusher and webhook_pusher.enabled and bus and neuron_mgr:
            def _push_neuron_fired_on_eval(event, _pusher=webhook_pusher, _mgr=neuron_mgr):
                """Push neuron_fired for neurons that crossed their threshold."""
                try:
                    last = _mgr.get_last_result()
                    if not last or not last.neuron_states:
                        return
                    all_neurons = _mgr.get_all_neurons()
                    for nid, neuron in all_neurons.items():
                        if not hasattr(neuron, "state") or not hasattr(neuron, "config"):
                            continue
                        if not neuron.state.active:
                            continue
                        layer = nid.split(".")[0] if "." in nid else "unknown"
                        _pusher.push_neuron_fired(
                            neuron_id=nid,
                            layer=layer,
                            value=neuron.state.value,
                            confidence=neuron.state.value,
                        )
                except Exception:
                    _LOGGER.debug("Neuron fired push failed", exc_info=True)

            bus.subscribe("neuron.evaluated", _push_neuron_fired_on_eval)
            _LOGGER.info("WebhookPusher neuron_fired push wired to neuron.evaluated event")
    except Exception:
        _LOGGER.exception("Failed to wire WebhookPusher neuron_fired push")

    # Wire WebhookPusher candidates_ranked push via IntegrationBus
    try:
        webhook_pusher = services.get("webhook_pusher")
        bus = services.get("integration_bus")
        candidate_store = services.get("candidate_store")
        if webhook_pusher and webhook_pusher.enabled and bus and candidate_store:
            def _push_candidates_on_eval(event, _pusher=webhook_pusher, _store=candidate_store):
                """Push top-10 ranked candidates after neuron evaluation."""
                try:
                    ranked = _store.list_ranked(limit=10, with_explanation=True)
                    if ranked:
                        compact = [
                            {
                                "id": c.get("id", ""),
                                "label": c.get("label", ""),
                                "kind": c.get("kind", ""),
                                "rank_score": c.get("rank_score", 0.0),
                                "explanation": c.get("explanation", "")[:200],
                            }
                            for c in ranked
                        ]
                        _pusher.push_candidate_ranked(compact)
                except Exception:
                    _LOGGER.debug("Candidates ranked push failed", exc_info=True)

            bus.subscribe("neuron.evaluated", _push_candidates_on_eval)
            _LOGGER.info("WebhookPusher candidates_ranked push wired to neuron.evaluated event")
    except Exception:
        _LOGGER.exception("Failed to wire WebhookPusher candidates_ranked push")

    # Wire WebhookPusher zone_mood push via IntegrationBus
    try:
        webhook_pusher = services.get("webhook_pusher")
        bus = services.get("integration_bus")
        if webhook_pusher and webhook_pusher.enabled and bus:
            def _push_zone_mood_on_eval(event, _pusher=webhook_pusher, _svcs=services):
                """Push per-zone mood adjustments after neuron evaluation."""
                try:
                    zone_auto = _svcs.get("zone_automation")
                    if not zone_auto:
                        return
                    # Iterate known zone configs
                    configs = getattr(zone_auto, "_configs", {})
                    for zone_id in configs:
                        try:
                            mood = zone_auto.get_mood(zone_id)
                            adjustment = zone_auto.get_mood_adjustment_for_zone(zone_id)
                            _pusher.push_zone_mood(
                                zone_id=zone_id,
                                mood=mood,
                                brightness_factor=float(adjustment.get("brightness_factor", 1.0)),
                                color_temp=int(adjustment.get("color_temp_k", 4000)),
                            )
                        except Exception:
                            pass
                except Exception:
                    _LOGGER.debug("Zone mood push failed", exc_info=True)

            bus.subscribe("neuron.evaluated", _push_zone_mood_on_eval)
            _LOGGER.info("WebhookPusher zone_mood push wired to neuron.evaluated event")
    except Exception:
        _LOGGER.exception("Failed to wire WebhookPusher zone_mood push")

    # Wire WebhookPusher brain_insight push via IntegrationBus
    try:
        webhook_pusher = services.get("webhook_pusher")
        bus = services.get("integration_bus")
        brain_graph = services.get("brain_graph_service")
        if webhook_pusher and webhook_pusher.enabled and bus and brain_graph:
            _insight_prev_edge_count = [0]

            def _push_brain_insight_on_eval(event, _pusher=webhook_pusher, _bg=brain_graph):
                """Push brain_insight when significant graph changes occur."""
                try:
                    stats = _bg.store.get_stats() if hasattr(_bg.store, "get_stats") else {}
                    edge_count = stats.get("edge_count", 0)
                    node_count = stats.get("node_count", 0)
                    prev = _insight_prev_edge_count[0]
                    # Only push when edge count changed by >= 5 (significant growth)
                    if prev > 0 and abs(edge_count - prev) >= 5:
                        _pusher.push_brain_insight("correlation", {
                            "node_count": node_count,
                            "edge_count": edge_count,
                            "edge_delta": edge_count - prev,
                        })
                    _insight_prev_edge_count[0] = edge_count
                except Exception:
                    _LOGGER.debug("Brain insight push failed", exc_info=True)

            bus.subscribe("neuron.evaluated", _push_brain_insight_on_eval)
            _LOGGER.info("WebhookPusher brain_insight push wired to neuron.evaluated event")
    except Exception:
        _LOGGER.exception("Failed to wire WebhookPusher brain_insight push")

    # Initialize AutonomyExecutor early (before bus wiring, v14.2.0 fix)
    try:
        from copilot_core.autonomy.executor import AutonomyExecutor
        from copilot_core.autonomy.ha_bridge import HABridge
        from copilot_core.autonomy.behavioral_log import BehavioralLog

        ha_bridge = HABridge()
        behavioral_log = BehavioralLog()

        autonomy_executor = AutonomyExecutor(
            zone_automation=services.get("zone_automation"),
            module_registry=services.get("module_registry"),
            ha_bridge=ha_bridge,
            behavioral_log=behavioral_log,
            light_intelligence=services.get("hub_light"),
            musikwolke_bridge=services.get("musikwolke_bridge"),
            neuron_manager=services.get("neuron_manager"),
            bus=services.get("integration_bus"),
        )
        services["autonomy_executor"] = autonomy_executor
        services["behavioral_log"] = behavioral_log
        _LOGGER.info("AutonomyExecutor initialized (pre-bus-wiring)")
    except Exception:
        _LOGGER.exception("Failed to init AutonomyExecutor (pre-bus-wiring)")

    # Wire services to IntegrationBus events
    _wire_bus_events(services)

    # Wire habitus auto-mining to event ingest pipeline
    _wire_habitus_auto_mining(services)

    # Initialize LLM Provider
    try:
        from copilot_core.llm_provider import LLMProvider
        services["llm_provider"] = LLMProvider()
        _LOGGER.info("LLMProvider initialized")
    except Exception:
        _LOGGER.exception("Failed to init LLMProvider")

    # Initialize Alarm Engine
    try:
        from copilot_core.alarm.engine import AlarmEngine
        services["alarm_engine"] = AlarmEngine(
            sonos_client=services.get("sonos_client"),
        )
        _LOGGER.info("AlarmEngine initialized")
    except Exception:
        _LOGGER.exception("Failed to init AlarmEngine")

    # Initialize Suggestion Engine
    try:
        from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine
        services["suggestion_engine"] = AutomationSuggestionEngine()
        _LOGGER.info("AutomationSuggestionEngine initialized")
    except Exception:
        _LOGGER.exception("Failed to init AutomationSuggestionEngine")

    # Calculate startup time
    services["startup_time_ms"] = (time.perf_counter() - start_time) * 1000
    
    # Add connection pool metrics to services
    try:
        from copilot_core.connection_pool import get_pool_metrics
        services["connection_pool_metrics"] = get_pool_metrics()
    except Exception:
        services["connection_pool_metrics"] = {"error": "Pool not initialized"}
    
    _LOGGER.info(
        f"Core services initialized in {services['startup_time_ms']:.2f}ms "
        f"(lazy_load_enabled={lazy_load_enabled}, connection_pooling=active)"
    )
    
    return services


def register_blueprints(app: Flask, services: dict) -> None:
    """
    Register all API blueprints with the Flask app.
    
    Args:
        app: Flask application instance
        services: Dictionary of initialized services
    """
    # Make services available via app.config for blueprints using current_app.config
    app.config["COPILOT_SERVICES"] = services

    # Install the single voice runtime access seam before any voice routes run.
    try:
        from copilot_core.voice.runtime_access import init_voice_runtime
        init_voice_runtime(app, services)
    except Exception:
        _LOGGER.exception("Failed to initialize voice runtime access seam")

    # ── Data-driven blueprint registration ────────────────────────────────
    # Each entry: (module_path, blueprint_attr, url_prefix_or_None)
    # url_prefix=None means the blueprint defines its own prefix internally.
    # NOTE: ALL blueprints are registered FLAT (not nested) so that a single
    # import failure does not take down all 40+ API routes.
    _BLUEPRINTS = [
        # Auth setup (unauthenticated — allows HA to fetch 1-Key-Flow token)
        ("copilot_core.api.v1.auth",             "auth_bp",              None),
        # Standalone blueprints with their own absolute prefix
        ("copilot_core.api.v1.log_fixer_tx",    "bp",                   None),
        ("copilot_core.api.v1.events_ingest",    "bp",                   "/api/v1"),
        ("copilot_core.api.v1.sensors",          "bp",                   None),
        ("copilot_core.api.v1.homekit",          "homekit_bp",           None),
        ("copilot_core.api.v1.anomaly",          "anomaly_bp",           "/api/v1"),
        ("copilot_core.api.v1.calendar",         "calendar_bp",          None),
        ("copilot_core.api.v1.analytics",          "analytics_bp",          None),
        ("copilot_core.api.v1.energy_forecast",  "energy_forecast_bp",   None),
        ("copilot_core.api.v1.plugins",           "bp",                   None),
        ("copilot_core.api.v1.tag_system",       "bp",                   None),
        ("copilot_core.api.v1.multihome",        "bp",                   None),
        ("copilot_core.api.v1.voice",            "bp",                   None),
        ("copilot_core.api.v1.habitus_zones",    "bp",                   None),
        # NOTE: sonos_bp is registered individually below (after init_sonos_api wiring)
        ("copilot_core.api.v1.module_control",   "module_control_bp",    None),
        ("copilot_core.api.v1.rag",              "bp",                   None),
        ("copilot_core.api.v1.styx_chat",        "bp",                   None),
        ("copilot_core.api.v1.mcp",              "bp",                   None),
        # ── Previously nested in api_v1 (blueprint.py) — now flat ──────
        # Blueprints with relative prefix: override to /api/v1/<prefix>
        ("copilot_core.api.v1.candidates",              "bp",               "/api/v1/candidates"),
        ("copilot_core.api.v1.events",                  "bp",               "/api/v1/events"),
        ("copilot_core.api.v1.mood",                    "bp",               "/api/v1/mood"),
        ("copilot_core.api.v1.graph",                   "bp",               "/api/v1/graph"),
        ("copilot_core.api.v1.habitus",                 "bp",               "/api/v1/habitus"),
        ("copilot_core.api.v1.habitus_dashboard_cards", "bp",               "/api/v1/habitus/dashboard_cards"),
        ("copilot_core.api.v1.graph_ops",               "bp",               "/api/v1/graph"),
        ("copilot_core.api.v1.vector",                  "bp",               "/api/v1/vector"),
        ("copilot_core.api.v1.neurons",                 "bp",               "/api/v1/neurons"),
        ("copilot_core.api.v1.neurons_visualization",   "bp",               "/api/v1/neurons"),
        ("copilot_core.api.v1.weather",                 "bp",               "/api/v1/weather"),
        ("copilot_core.api.v1.voice_context_bp",        "bp",               "/api/v1/voice"),
        ("copilot_core.api.v1.user_preferences",        "bp",               "/api/v1/user"),
        ("copilot_core.api.v1.dashboard",               "bp",               "/api/v1/dashboard"),
        ("copilot_core.knowledge_graph.api",             "bp",               "/api/v1/kg"),
        ("copilot_core.api.v1.search",                  "bp",               "/api/v1/search"),
        ("copilot_core.api.v1.notifications",           "bp",               "/api/v1/notifications"),
        ("copilot_core.api.v1.user_hints",              "bp",               "/api/v1/hints"),
        ("copilot_core.api.v1.conversation",            "conversation_bp",  "/api/v1/chat"),
        # Blueprints with None prefix: routes have /api/v1/ baked into paths
        ("copilot_core.api.v1.dev",                     "bp",               "/api/v1"),
        ("copilot_core.api.v1.swagger_ui",              "bp",               "/api/v1/docs"),
        ("copilot_core.api.v1.swagger_ui",              "openapi_bp",       "/api/v1"),
        ("copilot_core.sharing.api",                    "sharing_bp",       "/api/v1"),
        ("copilot_core.collective_intelligence.api",    "federated_bp",     "/api/v1"),
        ("copilot_core.api.v1.rate_limit",              "rate_limit_bp",    "/api/v1"),
        ("copilot_core.homeassistant.api",              "ha_discovery_bp",  "/api/v1"),
        ("copilot_core.api.v1.metrics",                 "metrics_bp",       "/api/v1"),
        # ── Stub blueprints for endpoints HA sensors poll ──────────
        ("copilot_core.api.v1.unifi_stub",              "unifi_stub_bp",    None),
        ("copilot_core.api.v1.regional_stub",           "regional_stub_bp", None),
    ]

    for module_path, bp_attr, prefix in _BLUEPRINTS:
        try:
            mod = importlib.import_module(module_path)
            bp = getattr(mod, bp_attr)
            if prefix is not None:
                app.register_blueprint(bp, url_prefix=prefix)
            else:
                app.register_blueprint(bp)
        except Exception:
            _LOGGER.exception("Failed to register blueprint %s.%s", module_path, bp_attr)

    # ── Blueprints requiring service wiring before registration ───────────

    # Zone Editor (needs hub_zones)
    try:
        from copilot_core.api.v1.zone_editor import zone_editor_bp, zone_editor_legacy_bp, init_zone_editor_api
        init_zone_editor_api(services.get("hub_zones"))
        app.register_blueprint(zone_editor_bp, url_prefix="/api/v1")
        app.register_blueprint(zone_editor_legacy_bp)
    except Exception:
        _LOGGER.exception("Failed to register zone_editor blueprints")

    # Habitus Zones init (blueprint already registered above)
    try:
        from copilot_core.api.v1.habitus_zones import init_habitus_zones_api
        init_habitus_zones_api(services.get("hub_zones"))
    except Exception:
        _LOGGER.exception("Failed to init habitus_zones API")

    # Media Zones (needs media_zone_manager + proactive_engine)
    try:
        from copilot_core.api.v1.media_zones import media_zones_bp, init_media_zones_api
        init_media_zones_api(
            media_mgr=services.get("media_zone_manager"),
            proactive_engine=services.get("proactive_engine"),
        )
        app.register_blueprint(media_zones_bp)  # uses own prefix /api/v1/media
    except Exception:
        _LOGGER.exception("Failed to register media_zones blueprint")

    # Module Control init (blueprint already registered above)
    try:
        from copilot_core.api.v1.module_control import init_module_control_api
        init_module_control_api(services.get("module_registry"))
    except Exception:
        _LOGGER.exception("Failed to init module_control API")

    # Register PilotSuite Module endpoints (Licht, Helligkeit, Heiz, Bewegung, Praesenz)
    try:
        from copilot_core.api.v1.module_endpoints import modules_bp
        app.register_blueprint(modules_bp)
    except Exception:
        _LOGGER.exception("Failed to register PilotSuite Module endpoints")

    # Register Integration Bus API
    try:
        from copilot_core.integration.api import integration_bp
        app.register_blueprint(integration_bp)
    except Exception:
        _LOGGER.exception("Failed to register integration_bp")

    # Register Neuron Layers Visualization API
    try:
        from copilot_core.api.v1.neuron_layers import neuron_layers_bp
        app.register_blueprint(neuron_layers_bp)
    except Exception:
        _LOGGER.exception("Failed to register neuron_layers_bp")

    # Register Module Health Dashboard API
    try:
        from copilot_core.api.v1.module_health import module_health_bp
        app.register_blueprint(module_health_bp)
    except Exception:
        _LOGGER.exception("Failed to register module_health_bp")

    # Register Suggestions API
    try:
        from copilot_core.api.v1.suggestions import suggestions_bp, init_suggestions_api
        init_suggestions_api(services.get("suggestion_engine"))
        app.register_blueprint(suggestions_bp)
    except Exception:
        _LOGGER.exception("Failed to register suggestions_bp")

    # Register Zone Automation API (presence-based light + music + entity management)
    from copilot_core.api.v1.zone_automation import zone_automation_bp, init_zone_automation_api
    try:
        from copilot_core.hub.zone_automation import ZoneAutomationController
        zone_auto_ctrl = ZoneAutomationController()
        services["zone_automation"] = zone_auto_ctrl
        init_zone_automation_api(zone_auto_ctrl)
    except Exception as exc:
        _LOGGER.warning("Zone Automation init failed: %s", exc)
        init_zone_automation_api(None)
    app.register_blueprint(zone_automation_bp)

    # Wire Musikwolke Bridge (connects ZoneAutomation → Sonos + MediaFollow)
    try:
        from copilot_core.hub.musikwolke_bridge import MusikwolkeBridge
        musikwolke = MusikwolkeBridge(
            sonos=services.get("sonos_client"),
            media_follow=services.get("hub_media"),
        )
        services["musikwolke_bridge"] = musikwolke
        # Connect bridge to ZoneAutomationController for auto-execution
        zone_ctrl = services.get("zone_automation")
        if zone_ctrl is not None:
            zone_ctrl.set_music_bridge(musikwolke)
            _LOGGER.info("MusikwolkeBridge connected to ZoneAutomationController")
        _LOGGER.info("MusikwolkeBridge wired (sonos=%s, media_follow=%s)",
                      services.get("sonos_client") is not None,
                      services.get("hub_media") is not None)
    except Exception:
        _LOGGER.exception("Failed to init MusikwolkeBridge")

    # Register Musikwolke API (zone-based Sonos control)
    from copilot_core.api.v1.musikwolke import musikwolke_bp, init_musikwolke_api
    init_musikwolke_api(services.get("musikwolke_bridge"))
    app.register_blueprint(musikwolke_bp)

    # Re-wire AutonomyExecutor with late-bound services (zone_automation, musikwolke_bridge)
    try:
        executor = services.get("autonomy_executor")
        if executor is not None:
            executor._zone_automation = services.get("zone_automation")
            executor._musikwolke_bridge = services.get("musikwolke_bridge")
            executor._light_intelligence = services.get("hub_light")
            _LOGGER.info("AutonomyExecutor re-wired with late-bound services")
    except Exception:
        _LOGGER.exception("Failed to re-wire AutonomyExecutor")

    # Register Autonomy API (zone-aware auto-execution dashboard)
    try:
        from copilot_core.api.v1.autonomy import autonomy_bp, init_autonomy_api
        init_autonomy_api(services.get("autonomy_executor"), services.get("module_registry"))
        app.register_blueprint(autonomy_bp)
    except Exception:
        _LOGGER.exception("Failed to register autonomy_bp")

    # Initialize Wecker (Smart Alarm) service
    try:
        from copilot_core.hub.wecker import WeckerService
        services["wecker"] = WeckerService(
            sonos_client=services.get("sonos_client"),
            config=services.get("config"),
        )
        _LOGGER.info("WeckerService initialized (sonos=%s)", services.get("sonos_client") is not None)
    except Exception:
        _LOGGER.exception("Failed to init WeckerService")

    # Register Wecker API
    from copilot_core.api.v1.wecker import bp as wecker_bp, init_wecker_bp
    init_wecker_bp(services.get("wecker"))
    app.register_blueprint(wecker_bp)

    # Register Zone Aggregates API (device-class-aware Sammelentitaeten + Zone Scenes)
    try:
        _dca = importlib.import_module("copilot_core.homeassistant.device_class_aggregator")
        ZoneAggregator = _dca.ZoneAggregator
        from copilot_core.api.v1.zone_aggregates import zone_aggregates_bp, init_zone_aggregates_api
        zone_aggregator = ZoneAggregator()
        services["zone_aggregator"] = zone_aggregator
        init_zone_aggregates_api(
            aggregator=zone_aggregator,
            zone_automation=services.get("zone_automation"),
            bus=services.get("integration_bus"),
        )
        app.register_blueprint(zone_aggregates_bp)
        _LOGGER.info("Zone Aggregates API registered")
    except Exception:
        _LOGGER.exception("Failed to register zone_aggregates_bp")

    # Register Zone Health API (per-zone health monitoring)
    try:
        from copilot_core.api.v1.zone_health import zone_health_bp, init_zone_health_api
        init_zone_health_api(
            zone_automation=services.get("zone_automation"),
            module_registry=services.get("module_registry"),
        )
        app.register_blueprint(zone_health_bp)
        _LOGGER.info("Zone Health API registered")
    except Exception:
        _LOGGER.exception("Failed to register zone_health_bp")

    # Register Zone Dashboard API (zonenzentriertes Dashboard mit voller Modulintegration)
    from copilot_core.api.v1.zone_dashboard import zone_dashboard_bp, init_zone_dashboard_api
    init_zone_dashboard_api(
        zone_automation=services.get("zone_automation"),
        mood_service=services.get("mood_service"),
        # 5 Basis-Module
        hub_licht=services.get("hub_licht"),
        hub_helligkeit=services.get("hub_helligkeit"),
        hub_heiz=services.get("hub_heiz"),
        hub_bewegung=services.get("hub_bewegung"),
        hub_praesenz=services.get("hub_praesenz"),
        # Intelligence-Engines
        hub_light_intel=services.get("hub_light"),
        hub_presence_intel=services.get("hub_presence"),
        hub_media=services.get("hub_media"),
        # Steuerungs-Engines
        hub_modes=services.get("hub_modes"),
        hub_scenes=services.get("hub_scenes"),
        hub_energy=services.get("hub_energy"),
        # Zusatz-Engines
        hub_notifications=services.get("hub_notifications"),
        hub_musikwolke=services.get("musikwolke_bridge"),
    )
    app.register_blueprint(zone_dashboard_bp)

    # Register Styx Dashboard API
    from copilot_core.api.v1.styx_dashboard import styx_dashboard_bp, init_styx_dashboard_api
    init_styx_dashboard_api(services)
    app.register_blueprint(styx_dashboard_bp)

    # Register Styx Voice API (STT + TTS)
    try:
        from copilot_core.api.v1.styx_voice import styx_voice_bp
        app.register_blueprint(styx_voice_bp)
    except Exception:
        _LOGGER.exception("Failed to register styx_voice_bp")

    # Serve Styx Dashboard SPA at /styx (injects auth token for 1-Key-Flow)
    @app.route("/styx")
    def _serve_styx_dashboard():
        from flask import render_template
        from copilot_core.api.security import get_auth_token
        return render_template("styx_dashboard.html", auth_token=get_auth_token())

    # Register Sonos API (native Sonos control via node-sonos-http-api)
    try:
        from copilot_core.api.v1.sonos import sonos_bp
        app.register_blueprint(sonos_bp)           # prefix: /api/v1/sonos
    except Exception:
        _LOGGER.exception("Failed to register sonos_bp")

    # Register Alarm API (Lichtwecker mit Sunrise/Sunset)
    try:
        from copilot_core.api.v1.alarm import alarm_bp, init_alarm_api
        init_alarm_api(services.get("alarm_engine"))
        app.register_blueprint(alarm_bp)           # prefix: /api/v1/alarm
    except Exception:
        _LOGGER.exception("Failed to register alarm_bp")

    # Register Conversation History API
    try:
        from copilot_core.api.v1.conversation_history import conversation_history_bp, init_conversation_history_api
        init_conversation_history_api(services.get("conversation_memory"))
        app.register_blueprint(conversation_history_bp)  # prefix: /api/v1/conversation
    except Exception:
        _LOGGER.exception("Failed to register conversation_history_bp")

    # Register Error Digest API
    try:
        from copilot_core.api.v1.error_digest import error_digest_bp, init_error_digest_api
        init_error_digest_api(llm_provider=services.get("llm_provider"))
        app.register_blueprint(error_digest_bp)    # prefix: /api/v1/errors
    except Exception:
        _LOGGER.exception("Failed to register error_digest_bp")

    # Register PilotSuite Hub API (standalone, absolute prefix /api/v1/hub)
    try:
        from copilot_core.hub.api import hub_bp
        app.register_blueprint(hub_bp)
    except Exception:
        _LOGGER.exception("Failed to register hub_bp")

    # NOTE: sharing_bp and federated_bp are already nested in api_v1
    # (via blueprint.py lines 79-80). No standalone registration needed.

    # ── Additional standalone blueprints (data-driven) ──────────────────
    _EXTRA_BLUEPRINTS = [
        ("copilot_core.api.v1.debug",             "bp",                  "/api/v1"),
        ("copilot_core.api.v1.entity_adoption",    "bp",                  "/api/v1"),
        ("copilot_core.api.v1.performance",        "performance_bp",      "/api/v1"),
        # Blueprints with built-in prefix
        ("copilot_core.api.v1.entity_assignment",  "entity_assignment_bp", None),
        ("copilot_core.api.v1.haushalt",           "haushalt_bp",          None),
        ("copilot_core.api.v1.onyx_bridge",        "onyx_bridge_bp",       None),
        ("copilot_core.api.v1.predictive",         "predictive_bp",        None),
        ("copilot_core.api.v1.presence",           "presence_bp",          None),
        ("copilot_core.api.v1.scenes",             "scenes_bp",            None),
        ("copilot_core.api.v1.shopping",           "shopping_bp",          None),
        # Agent config (HA calls /api/v1/agent/status, /api/v1/agent/verify, etc.)
        ("copilot_core.agent_config",              "agent_config_bp",      None),
        # Comfort stub (HA calls /api/v1/comfort, /api/v1/comfort/lighting)
        ("copilot_core.api.v1.comfort_stub",       "comfort_stub_bp",      None),
        # Network + HA Integration Module blueprints (built-in prefix)
        ("copilot_core.api.v1.zwave_module",       "zwave_module_bp",      None),
        ("copilot_core.api.v1.zigbee_module",      "zigbee_module_bp",     None),
        ("copilot_core.api.v1.thread_module",      "thread_module_bp",     None),
        ("copilot_core.api.v1.ha_module",           "ha_module_bp",         None),
        ("copilot_core.api.v1.module_router_api",  "module_router_bp",     None),
        # Multi-user conflict resolution
        ("copilot_core.api.v1.conflict_resolution", "bp",                   None),
        # ML Pipeline API (training, inference, model management)
        ("copilot_core.api.v1.ml_pipeline",         "bp",                   None),
        # Character API (Styx personality management)
        ("copilot_core.api.v1.character",           "bp",                   None),
        # Action Attribution API
        ("copilot_core.api.v1.action_attribution",  "bp",                   None),
        # user_hints: registered via api/v1/blueprint.py — skip
    ]

    for module_path, bp_attr, prefix in _EXTRA_BLUEPRINTS:
        try:
            mod = importlib.import_module(module_path)
            bp = getattr(mod, bp_attr)
            if prefix is not None:
                app.register_blueprint(bp, url_prefix=prefix)
            else:
                app.register_blueprint(bp)
        except Exception:
            _LOGGER.exception("Failed to register blueprint %s.%s", module_path, bp_attr)

    # ── Blueprints requiring service wiring ───────────────────────────────

    # Automation API
    try:
        from copilot_core.api.v1.automation_api import automation_bp, init_automation_api
        init_automation_api(services.get("automation_creator"))
        app.register_blueprint(automation_bp, url_prefix="/api/v1")
    except Exception:
        _LOGGER.exception("Failed to register automation_bp")

    # Automations Suggestion API (/api/v1/automations/*)
    try:
        from copilot_core.automations.api import automations_bp, init_automations_api
        init_automations_api(services.get("suggestion_engine"))
        app.register_blueprint(automations_bp)
    except Exception:
        _LOGGER.exception("Failed to register automations_bp")

    # Onboarding API (/api/v1/onboarding/*)
    try:
        from copilot_core.onboarding import onboarding_bp, init_onboarding
        init_onboarding(services.get("config"))
        app.register_blueprint(onboarding_bp)
    except Exception:
        _LOGGER.exception("Failed to register onboarding_bp")

    # Cache Control API
    try:
        from copilot_core.api.v1.cache_control import cache_control_bp, init_cache_control_api
        init_cache_control_api()
        app.register_blueprint(cache_control_bp, url_prefix="/api/v1/cache")
    except Exception:
        _LOGGER.exception("Failed to register cache_control_bp")

    # Explain API (explainability for suggestions/patterns)
    try:
        from copilot_core.api.v1.explain import explain_bp, init_explain_api
        from copilot_core.explainability import ExplainabilityEngine
        explain_engine = ExplainabilityEngine(
            brain_graph_service=services.get("brain_graph_service"),
        )
        services["explainability_engine"] = explain_engine
        init_explain_api(explain_engine)
        app.register_blueprint(explain_bp)
    except Exception:
        _LOGGER.exception("Failed to register explain_bp")

    # Reminders API (waste + birthday reminders)
    try:
        from copilot_core.api.v1.reminders import reminders_bp, init_reminders_api
        init_reminders_api(
            waste_service=services.get("waste_service"),
            birthday_service=services.get("birthday_service"),
        )
        app.register_blueprint(reminders_bp)
    except Exception:
        _LOGGER.exception("Failed to register reminders_bp")

    # OpenAI-compatible endpoints (/v1/chat/completions, /v1/models)
    try:
        from copilot_core.api.v1.conversation import openai_compat_bp
        app.register_blueprint(openai_compat_bp)
    except Exception:
        _LOGGER.exception("Failed to register openai_compat_bp")

    # MCP Server (JSON-RPC 2.0 at /mcp)
    try:
        from copilot_core.mcp_server import mcp_bp
        app.register_blueprint(mcp_bp)
    except Exception:
        _LOGGER.exception("Failed to register mcp_bp")

    _LOGGER.info("All API blueprints registered")


async def cleanup_services(services: dict) -> None:
    """
    Cleanup all services and connection pools on shutdown.
    
    Args:
        services: Dictionary of initialized services
    """
    _LOGGER.info("Cleaning up services...")
    
    # Close connection pools FIRST (before closing services that may use them)
    try:
        from copilot_core.connection_pool import close_pool
        await close_pool()
        _LOGGER.info("Connection pools closed")
    except Exception:
        _LOGGER.exception("Failed to close connection pools")
    
    # Close high-level connections
    try:
        from copilot_core.connections import close_all_connections
        await close_all_connections()
        _LOGGER.info("All connections closed")
    except Exception:
        _LOGGER.exception("Failed to close connections")
    
    _LOGGER.info("Service cleanup complete")


# Import required modules at module level (these are lightweight)
from copilot_core.api.v1 import log_fixer_tx
from copilot_core.api.v1 import events_ingest
from copilot_core.api.v1.events_ingest import set_post_ingest_callback
from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.brain_graph.store import BrainGraphStore

# Alias for backwards compatibility
GraphStore = BrainGraphStore
from copilot_core.brain_graph.render import GraphRenderer
from copilot_core.ingest.event_processor import EventProcessor
from copilot_core.candidates.store import CandidateStore
from copilot_core.habitus.service import HabitusService
from copilot_core.mood.service import MoodService
from copilot_core.system_health.service import SystemHealthService
from copilot_core.unifi.service import UniFiService
from copilot_core.tags import TagRegistry, create_tag_service
from copilot_core.webhook_pusher import WebhookPusher
from copilot_core.household import HouseholdProfile
from copilot_core.neurons.manager import NeuronManager
from copilot_core.module_registry import ModuleRegistry
from copilot_core.automation_creator import AutomationCreator
from copilot_core.media_zone_manager import MediaZoneManager
from copilot_core.hub.sonos_client import SonosCloudClient
from copilot_core.waste_service import WasteCollectionService, BirthdayService
