"""
Core Setup - Service initialization and blueprint registration.

Optimized for performance with lazy loading support for heavy modules.
Startup time target: <2s (from ~5s)

Features:
- Lazy loading for Energy, ML, Calendar modules
- Configurable via lazy_load_enabled flag
- Performance metrics tracking
- Memory optimization: only load modules when needed
"""

import logging
import time
from typing import Dict, Any, Optional
from flask import Flask

_LOGGER = logging.getLogger(__name__)


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
        "mood_service": None,
        "event_processor": None,
        "tag_registry": None,
        "webhook_pusher": None,
        "household_profile": None,
        "neuron_manager": None,
        "conversation_memory": None,
        "telegram_bot": None,
        "module_registry": None,
        "automation_creator": None,
        "media_zone_manager": None,
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
        init_brain_graph_api(brain_graph_service, services["graph_renderer"])
    except Exception:
        _LOGGER.exception("Failed to init BrainGraphService")

    # Initialize dev surface
    try:
        if services["brain_graph_service"]:
            init_dev_surface_api(services["brain_graph_service"])
    except Exception:
        _LOGGER.exception("Failed to init DevSurface")

    # Initialize candidates API and store
    try:
        candidate_store = CandidateStore()
        services["candidate_store"] = candidate_store
        init_candidates_api(candidate_store)
    except Exception:
        _LOGGER.exception("Failed to init CandidateStore")

    # Initialize habitus service and API
    try:
        if services["brain_graph_service"] and services["candidate_store"]:
            habitus_service = HabitusService(services["brain_graph_service"], services["candidate_store"])
            services["habitus_service"] = habitus_service
            init_habitus_api(habitus_service)
    except Exception:
        _LOGGER.exception("Failed to init HabitusService")

    # Initialize mood service and API
    try:
        mood_service = MoodService()
        services["mood_service"] = mood_service
        init_mood_api(mood_service)
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

    # Initialize Webhook Pusher
    try:
        webhook_url = config.get("webhook_url", "") if config else ""
        webhook_token = config.get("webhook_token", "") if config else ""
        services["webhook_pusher"] = WebhookPusher(webhook_url, webhook_token)
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
            neuron_manager.on_mood_change(
                lambda mood, conf: webhook_pusher.push_mood_changed(mood, conf)
            )
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
                # services["telegram_bot"] = TelegramBot(telegram_config)
                pass
    except Exception:
        _LOGGER.exception("Failed to init TelegramBot")

    # Initialize Module Registry
    try:
        services["module_registry"] = ModuleRegistry()
    except Exception:
        _LOGGER.exception("Failed to init ModuleRegistry")

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

    # Initialize Proactive Engine with lazy loading
    try:
        if lazy_load_enabled:
            from copilot_core.utils.lazy_loader import proactive_engine_loader
            services["proactive_engine"] = proactive_engine_loader
            _LOGGER.debug("ProactiveContextEngine deferred via lazy loader")
        else:
            # services["proactive_engine"] = ProactiveContextEngine()
            pass
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
            # services["web_search_service"] = WebSearchService()
            pass
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
    # Import blueprints
    from copilot_core.api.v1.log_fixer_tx import bp as log_fixer_bp
    from copilot_core.api.v1.events_ingest import bp as events_ingest_bp
    from copilot_core.api.v1.sensors import bp as sensors_bp
    from copilot_core.api.v1.homekit import homekit_bp
    from copilot_core.api.v1.anomaly import anomaly_bp
    from copilot_core.api.v1.metrics import metrics_bp
    from copilot_core.api.v1.calendar import calendar_bp
    from copilot_core.api.v1.energy_forecast import energy_forecast_bp
    from copilot_core.api.v1.habitus import bp as habitus_bp
    from copilot_core.api.v1.habitus_zones import bp as habitus_zones_bp
    from copilot_core.api.v1.mood import bp as mood_bp
    from copilot_core.api.v1.zone_editor import zone_editor_bp
    from copilot_core.api.v1.media_zones import media_zones_bp
    from copilot_core.api.v1.tag_system import bp as tag_bp
    from copilot_core.api.v1.notifications import bp as notifications_bp
    from copilot_core.api.v1.blueprint import api_v1 as blueprint_bp
    from copilot_core.api.v1.multihome import bp as multihome_bp
    from copilot_core.api.v1.module_control import module_control_bp
    from copilot_core.api.v1.user_preferences import bp as user_preferences_bp
    from copilot_core.api.v1.mcp import bp as mcp_bp
    # api_v1.register_blueprint(module_control_bp)  # Can't use api_v1 because module_control_bp has absolute prefix
    from copilot_core.api.v1.voice import bp as voice_bp
    from copilot_core.api.v1.vector import bp as vector_bp
    from copilot_core.api.v1.swagger_ui import bp as swagger_ui_bp
    from copilot_core.api.v1.rag import bp as rag_bp
    from copilot_core.api.v1.styx_chat import bp as styx_bp
    
    # Register blueprints
    app.register_blueprint(log_fixer_bp, url_prefix="/api/v1")
    app.register_blueprint(events_ingest_bp, url_prefix="/api/v1")
    app.register_blueprint(sensors_bp, url_prefix="/api/v1")
    app.register_blueprint(homekit_bp, url_prefix="/api/v1")
    app.register_blueprint(anomaly_bp, url_prefix="/api/v1")
    # metrics_bp registered via api_v1 blueprint (copilot_core.api.v1.blueprint)
    # app.register_blueprint(metrics_bp, url_prefix="/api/v1")  # Removed - duplicate
    app.register_blueprint(calendar_bp, url_prefix="/api/v1")
    app.register_blueprint(energy_forecast_bp, url_prefix="/api/v1")
    app.register_blueprint(habitus_bp, url_prefix="/api/v1")
    app.register_blueprint(habitus_zones_bp)  # Already has /api/v1/habitus/zones prefix
    app.register_blueprint(mood_bp, url_prefix="/api/v1")
    app.register_blueprint(zone_editor_bp, url_prefix="/api/v1")
    app.register_blueprint(media_zones_bp, url_prefix="/api/v1")
    app.register_blueprint(tag_bp, url_prefix="/api/v1")
    app.register_blueprint(notifications_bp, url_prefix="/api/v1")
    app.register_blueprint(blueprint_bp, url_prefix="/api/v1")
    app.register_blueprint(multihome_bp, url_prefix="/api/v1")
    # module_control_bp has url_prefix="/api/v1/modules" (absolute), register directly
    app.register_blueprint(module_control_bp)
    app.register_blueprint(user_preferences_bp, url_prefix="/api/v1")
    app.register_blueprint(voice_bp, url_prefix="/api/v1")
    app.register_blueprint(vector_bp, url_prefix="/api/v1")
    app.register_blueprint(swagger_ui_bp, url_prefix="/api/v1")
    app.register_blueprint(rag_bp)  # Already has /api/v1/rag prefix
    app.register_blueprint(styx_bp)  # Already has /api/styx prefix
    
    # Register MCP REST API (standalone, absolute prefix /api/v1/mcp)
    app.register_blueprint(mcp_bp)
    
    # Register PilotSuite Phase 5 APIs
    from copilot_core.sharing.api import sharing_bp
    from copilot_core.collective_intelligence.api import federated_bp
    
    app.register_blueprint(sharing_bp, url_prefix="/api/v1")
    app.register_blueprint(federated_bp, url_prefix="/api/v1")
    
    _LOGGER.info("API blueprints registered")


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
from copilot_core.brain_graph.api import brain_graph_bp, init_brain_graph_api
from copilot_core.brain_graph.service import BrainGraphService
from copilot_core.brain_graph.store import BrainGraphStore

# Alias for backwards compatibility
GraphStore = BrainGraphStore
from copilot_core.brain_graph.render import GraphRenderer
from copilot_core.ingest.event_processor import EventProcessor
from copilot_core.dev_surface.api import dev_surface_bp, init_dev_surface_api
from copilot_core.candidates.api import candidates_bp, init_candidates_api
from copilot_core.candidates.store import CandidateStore
from copilot_core.habitus.api import habitus_bp, init_habitus_api
from copilot_core.habitus.service import HabitusService
from copilot_core.mood.api import mood_bp, init_mood_api
from copilot_core.mood.service import MoodService
from copilot_core.system_health.api import system_health_bp
from copilot_core.system_health.service import SystemHealthService
from copilot_core.unifi.api import unifi_bp, set_unifi_service
from copilot_core.unifi.service import UniFiService
from copilot_core.tags import TagRegistry, create_tag_service
from copilot_core.tags.api import init_tags_api as setup_tag_api
from copilot_core.webhook_pusher import WebhookPusher
from copilot_core.household import HouseholdProfile
from copilot_core.neurons.manager import NeuronManager
from copilot_core.module_registry import ModuleRegistry
from copilot_core.automation_creator import AutomationCreator
from copilot_core.media_zone_manager import MediaZoneManager
from copilot_core.waste_service import WasteCollectionService, BirthdayService
