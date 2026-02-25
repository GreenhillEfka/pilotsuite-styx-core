"""
Core Setup - Service initialization and blueprint registration.

Extracted from main.py to follow modular architecture pattern.
"""

import logging
import os
from flask import Flask

from copilot_core.error_boundary import ModuleErrorBoundary

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
from copilot_core.energy.api import energy_bp, init_energy_api
from copilot_core.energy.service import EnergyService
# Tag System v0.2 (Decision Matrix 2026-02-14)
from copilot_core.tags import TagRegistry, create_tag_service
from copilot_core.tags.api import init_tags_api as setup_tag_api
from copilot_core.webhook_pusher import WebhookPusher
from copilot_core.household import HouseholdProfile
from copilot_core.neurons.manager import NeuronManager

# SearXNG web search integration (v7.11.1)
_SEARXNG_ENABLED = os.environ.get("SEARXNG_ENABLED", "false").lower() == "true"
_SEARXNG_BASE_URL = os.environ.get("SEARXNG_BASE_URL", "http://192.168.30.18:4041")

# PilotSuite Phase 5 APIs
from copilot_core.sharing.api import sharing_bp
from copilot_core.api.v1.notifications import bp as notifications_bp
from copilot_core.collective_intelligence.api import federated_bp
from copilot_core.telegram import TelegramBot
from copilot_core.module_registry import ModuleRegistry
from copilot_core.automation_creator import AutomationCreator
from copilot_core.media_zone_manager import MediaZoneManager
from copilot_core.proactive_engine import ProactiveContextEngine
from copilot_core.web_search import WebSearchService
from copilot_core.waste_service import WasteCollectionService, BirthdayService

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


def init_services(hass=None, config: dict = None):
    """
    Initialize all core services and return them as a dict for testing/dependency injection.

    Each service block is wrapped in try/except so a single failure does not
    prevent the remaining services from starting.
    """
    config = config or {}

    services: dict = {
        "config": config,
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

    # Initialize energy service (requires hass)
    try:
        if hass:
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
    # When media_player events arrive, derive mood context from them
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

    # Initialize LLM Provider (v7.11.1 — SearXNG web search)
    try:
        from copilot_core.llm_provider import LLMProvider
        services["llm_provider"] = LLMProvider()
        _LOGGER.info("LLM Provider initialized (SearXNG: %s)", _SEARXNG_ENABLED if _SEARXNG_ENABLED else "not configured")
    except Exception:
        _LOGGER.exception("Failed to init LLMProvider")

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

    # NeuronManager: Household-Profil setzen, configure_from_ha, und Webhook-Callbacks registrieren
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

    # Set conversation env vars from config (used by conversation.py + llm_provider.py)
    try:
        import os
        conv_config = config.get("conversation", {}) if config else {}
        if conv_config.get("ollama_url"):
            os.environ.setdefault("OLLAMA_URL", conv_config["ollama_url"])
        if conv_config.get("ollama_model"):
            os.environ.setdefault("OLLAMA_MODEL", conv_config["ollama_model"])
        if conv_config.get("assistant_name"):
            os.environ.setdefault("ASSISTANT_NAME", conv_config["assistant_name"])
        if conv_config.get("character"):
            os.environ.setdefault("CONVERSATION_CHARACTER", conv_config["character"])
        if conv_config.get("enabled"):
            os.environ.setdefault("CONVERSATION_ENABLED", "true")
        # Cloud fallback config (OpenClaw, OpenAI, etc.)
        if conv_config.get("cloud_api_url"):
            os.environ.setdefault("CLOUD_API_URL", conv_config["cloud_api_url"])
        if conv_config.get("cloud_api_key"):
            os.environ.setdefault("CLOUD_API_KEY", conv_config["cloud_api_key"])
        if conv_config.get("cloud_model"):
            os.environ.setdefault("CLOUD_MODEL", conv_config["cloud_model"])
        if conv_config.get("prefer_local") is not None:
            os.environ.setdefault("PREFER_LOCAL", str(conv_config["prefer_local"]).lower())
    except Exception:
        _LOGGER.exception("Failed to set conversation env vars")

    # Initialize Module Registry (v1.3.0 — persistent module state control)
    try:
        module_registry = ModuleRegistry()
        services["module_registry"] = module_registry
        _LOGGER.info("ModuleRegistry initialized (SQLite persistence)")
    except Exception:
        _LOGGER.exception("Failed to init ModuleRegistry")

    # Initialize Automation Creator (v1.3.0 — create HA automations from suggestions)
    try:
        automation_creator = AutomationCreator()
        services["automation_creator"] = automation_creator
        _LOGGER.info("AutomationCreator initialized")
    except Exception:
        _LOGGER.exception("Failed to init AutomationCreator")

    # Initialize Media Zone Manager (v3.1.0)
    try:
        media_zone_manager = MediaZoneManager()
        services["media_zone_manager"] = media_zone_manager
        _LOGGER.info("MediaZoneManager initialized")
    except Exception:
        _LOGGER.exception("Failed to init MediaZoneManager")

    # NOTE: ProactiveContextEngine moved below waste/birthday init (v3.2.3)

    # Initialize Web Search Service (v3.1.0 -- news, search, regional warnings)
    try:
        search_config = config.get("web_search", {}) if config else {}
        web_search_service = WebSearchService(
            ags_code=search_config.get("ags_code", ""),
        )
        services["web_search_service"] = web_search_service
        _LOGGER.info("WebSearchService initialized (NINA + DWD + DDG)")
    except Exception:
        _LOGGER.exception("Failed to init WebSearchService")

    # Initialize Waste Collection Service (v3.2.0)
    try:
        waste_service = WasteCollectionService()
        services["waste_service"] = waste_service
        _LOGGER.info("WasteCollectionService initialized")
    except Exception:
        _LOGGER.exception("Failed to init WasteCollectionService")

    # Initialize Birthday Service (v3.2.0)
    try:
        birthday_service = BirthdayService()
        services["birthday_service"] = birthday_service
        _LOGGER.info("BirthdayService initialized")
    except Exception:
        _LOGGER.exception("Failed to init BirthdayService")

    # Initialize Proactive Context Engine (v3.2.3 -- moved after waste/birthday)
    try:
        proactive_engine = ProactiveContextEngine(
            media_zone_manager=services.get("media_zone_manager"),
            mood_service=services.get("mood_service"),
            household_profile=services.get("household_profile"),
            conversation_memory=services.get("conversation_memory"),
            waste_service=services.get("waste_service"),
            birthday_service=services.get("birthday_service"),
            habitus_service=services.get("habitus_service"),
        )
        services["proactive_engine"] = proactive_engine
        _LOGGER.info("ProactiveContextEngine initialized (with presence triggers)")
    except Exception:
        _LOGGER.exception("Failed to init ProactiveContextEngine")

    # ── PilotSuite Hub — All 17 engines (v7.6.1 — granular fault isolation) ──

    # Step 1: Import Hub module (if this fails, no engines can load)
    _hub_available = False
    try:
        from copilot_core.hub import (
            DashboardHub,
            PluginManager,
            MultiHomeManager,
            PredictiveMaintenanceEngine,
            AnomalyDetectionEngine,
            HabitusZoneEngine,
            LightIntelligenceEngine,
            ZoneModeEngine,
            MediaFollowEngine,
            EnergyAdvisorEngine,
            AutomationTemplateEngine,
            SceneIntelligenceEngine,
            PresenceIntelligenceEngine,
            NotificationIntelligenceEngine,
            SystemIntegrationHub,
            BrainArchitectureEngine,
            BrainActivityEngine,
        )
        _hub_available = True
    except Exception:
        _LOGGER.exception(
            "Failed to import Hub module — ALL Hub engines disabled. "
            "Check for syntax errors in copilot_core/hub/ files."
        )

    # Step 2: Instantiate each engine individually (one failure won't kill others)
    if _hub_available:
        _hub_engines = {
            "hub_dashboard": (DashboardHub, "DashboardHub"),
            "hub_plugin_manager": (PluginManager, "PluginManager"),
            "hub_multi_home": (MultiHomeManager, "MultiHomeManager"),
            "hub_maintenance": (PredictiveMaintenanceEngine, "PredictiveMaintenanceEngine"),
            "hub_anomaly": (AnomalyDetectionEngine, "AnomalyDetectionEngine"),
            "hub_zones": (HabitusZoneEngine, "HabitusZoneEngine"),
            "hub_light": (LightIntelligenceEngine, "LightIntelligenceEngine"),
            "hub_modes": (ZoneModeEngine, "ZoneModeEngine"),
            "hub_media": (MediaFollowEngine, "MediaFollowEngine"),
            "hub_energy": (EnergyAdvisorEngine, "EnergyAdvisorEngine"),
            "hub_templates": (AutomationTemplateEngine, "AutomationTemplateEngine"),
            "hub_scenes": (SceneIntelligenceEngine, "SceneIntelligenceEngine"),
            "hub_presence": (PresenceIntelligenceEngine, "PresenceIntelligenceEngine"),
            "hub_notifications": (NotificationIntelligenceEngine, "NotificationIntelligenceEngine"),
            "hub_integration": (SystemIntegrationHub, "SystemIntegrationHub"),
            "hub_brain_arch": (BrainArchitectureEngine, "BrainArchitectureEngine"),
            "hub_brain_activity": (BrainActivityEngine, "BrainActivityEngine"),
        }
        _engines_ok = 0
        for svc_key, (cls, cls_name) in _hub_engines.items():
            try:
                services[svc_key] = cls()
                _engines_ok += 1
            except Exception:
                _LOGGER.exception("Failed to init %s — this engine will be unavailable", cls_name)

        _LOGGER.info("Hub engines: %d/%d initialized", _engines_ok, len(_hub_engines))

    # Step 3: Wire Integration Hub (only if it was created)
    integration_hub = services.get("hub_integration")
    if integration_hub is not None:
        _engine_map = {
            "dashboard": services.get("hub_dashboard"),
            "plugin_manager": services.get("hub_plugin_manager"),
            "multi_home": services.get("hub_multi_home"),
            "predictive_maintenance": services.get("hub_maintenance"),
            "anomaly_detection": services.get("hub_anomaly"),
            "habitus_zones": services.get("hub_zones"),
            "light_intelligence": services.get("hub_light"),
            "zone_modes": services.get("hub_modes"),
            "media_follow": services.get("hub_media"),
            "energy_advisor": services.get("hub_energy"),
            "automation_templates": services.get("hub_templates"),
            "scene_intelligence": services.get("hub_scenes"),
            "presence_intelligence": services.get("hub_presence"),
            "notification_intelligence": services.get("hub_notifications"),
        }
        for name, engine in _engine_map.items():
            if engine is not None:
                try:
                    integration_hub.register_engine(name, engine)
                except Exception:
                    _LOGGER.exception("Failed to register engine '%s' with Integration Hub", name)

        try:
            wire_count = integration_hub.auto_wire()
            _LOGGER.info("Integration Hub: %d event subscriptions auto-wired", wire_count)
        except Exception:
            _LOGGER.exception("Failed to auto-wire Integration Hub")

    # Step 4: Sync Brain Architecture (only if both exist)
    brain_arch = services.get("hub_brain_arch")
    if brain_arch is not None and integration_hub is not None:
        try:
            brain_arch.sync_with_hub(integration_hub)
            _LOGGER.info("Brain Architecture synced with Integration Hub")
        except Exception:
            _LOGGER.exception("Failed to sync Brain Architecture with Integration Hub")

    _LOGGER.info(
        "PilotSuite Hub init complete: %d engines, integration=%s, brain=%s",
        sum(1 for k in services if k.startswith("hub_") and services[k] is not None),
        integration_hub is not None,
        brain_arch is not None,
    )

    # Initialize Telegram Bot (requires conversation to be configured)
    try:
        tg_config = config.get("telegram", {}) if config else {}
        tg_token = tg_config.get("token", "").strip()
        if tg_config.get("enabled") and tg_token:
            # Validate token format before attempting connection
            if not TelegramBot.validate_token(tg_token):
                _LOGGER.error(
                    "Telegram token format invalid — expected <bot_id>:<hash> from @BotFather"
                )
            else:
                from copilot_core.api.v1.conversation import process_with_tool_execution
                bot = TelegramBot(
                    token=tg_token,
                    allowed_chat_ids=tg_config.get("allowed_chat_ids", []),
                )
                # Verify token with Telegram API before starting poll loop
                if bot.verify_token():
                    bot.set_chat_handler(process_with_tool_execution)
                    bot.start()
                    services["telegram_bot"] = bot
                    acl_info = (
                        f"{len(bot.allowed_chat_ids)} allowed chat IDs"
                        if bot.allowed_chat_ids
                        else "all chats allowed"
                    )
                    _LOGGER.info(
                        "Telegram bot started (token=***%s, %s)",
                        tg_token[-4:],
                        acl_info,
                    )
                else:
                    _LOGGER.error(
                        "Telegram bot token rejected by API — check token in addon config"
                    )
        elif tg_config.get("enabled"):
            _LOGGER.warning("Telegram enabled but no token configured — skipping bot startup")
    except Exception:
        _LOGGER.exception("Failed to init Telegram bot")

    return services


def register_blueprints(app: Flask, services: dict = None) -> None:
    """
    Register all API blueprints with the Flask app.
    
    Args:
        app: Flask application instance
        services: Optional services dict from init_services() for global access
    """
    # Import performance blueprint
    from copilot_core.api.performance import performance_bp
    
    app.register_blueprint(log_fixer_tx.bp)
    app.register_blueprint(events_ingest.bp)
    app.register_blueprint(brain_graph_bp)
    app.register_blueprint(dev_surface_bp)
    app.register_blueprint(candidates_bp)
    app.register_blueprint(habitus_bp)
    app.register_blueprint(mood_bp)
    app.register_blueprint(system_health_bp)
    app.register_blueprint(unifi_bp)
    app.register_blueprint(energy_bp)
    app.register_blueprint(performance_bp)  # Performance monitoring

    # Register Conversation/LLM API (Ollama, default qwen3:0.6b)
    try:
        from copilot_core.api.v1.conversation import conversation_bp, openai_compat_bp
        app.register_blueprint(conversation_bp)
        app.register_blueprint(openai_compat_bp)
        _LOGGER.info("Registered conversation API (/chat/* and /v1/*)")
    except Exception:
        _LOGGER.exception("Failed to register conversation blueprint")

    # Register Styx Agent Config API (/api/v1/agent/*)
    try:
        from copilot_core.agent_config import agent_config_bp, init_agent_config
        init_agent_config(config=services.get("config", {}) if services else {})
        app.register_blueprint(agent_config_bp)
        _LOGGER.info("Registered agent config API (/api/v1/agent/*)")
    except Exception:
        _LOGGER.exception("Failed to register agent config API")

    # Register Tag System v0.2 blueprint (Decision Matrix 2026-02-14)
    # init_tags_api sets the global registry; the bp is already defined in tags/api.py
    if services and services.get("tag_registry"):
        setup_tag_api(services["tag_registry"])
    from copilot_core.tags.api import bp as tags_bp
    app.register_blueprint(tags_bp)

    # Register Telegram Bot API
    from copilot_core.telegram.api import telegram_bp, init_telegram_api
    if services and services.get("telegram_bot"):
        init_telegram_api(services["telegram_bot"])
    app.register_blueprint(telegram_bp)

    # Register Module Control API (v1.3.0)
    from copilot_core.api.v1.module_control import module_control_bp, init_module_control_api
    if services and services.get("module_registry"):
        init_module_control_api(services["module_registry"])
    app.register_blueprint(module_control_bp)

    # Register Automation API (v1.3.0)
    from copilot_core.api.v1.automation_api import automation_bp, init_automation_api
    if services and services.get("automation_creator"):
        init_automation_api(services["automation_creator"])
    app.register_blueprint(automation_bp)

    # Register Explainability API (v2.1.0)
    try:
        from copilot_core.api.v1.explain import explain_bp, init_explain_api
        from copilot_core.explainability import ExplainabilityEngine
        engine = ExplainabilityEngine(
            brain_graph_service=services.get("brain_graph_service") if services else None
        )
        init_explain_api(engine)
        app.register_blueprint(explain_bp)
    except Exception:
        _LOGGER.exception("Failed to register Explainability API")

    # Register Prediction API (v2.2.0, extended v5.0.0 — timeseries + load shifting)
    try:
        from copilot_core.prediction.api import prediction_bp, init_prediction_api
        from copilot_core.prediction.forecaster import ArrivalForecaster
        from copilot_core.prediction.energy_optimizer import EnergyOptimizer, LoadShiftingScheduler
        from copilot_core.prediction.timeseries import MoodTimeSeriesForecaster
        _optimizer = EnergyOptimizer()
        init_prediction_api(
            ArrivalForecaster(),
            _optimizer,
            MoodTimeSeriesForecaster(),
            LoadShiftingScheduler(_optimizer),
        )
        app.register_blueprint(prediction_bp)
    except Exception:
        _LOGGER.exception("Failed to register Prediction API")

    # Register Media Zones + Proactive API (v3.1.0)
    try:
        from copilot_core.api.v1.media_zones import media_zones_bp, init_media_zones_api
        if services:
            init_media_zones_api(
                services.get("media_zone_manager"),
                services.get("proactive_engine"),
            )
        app.register_blueprint(media_zones_bp)
        _LOGGER.info("Registered Media Zones API (/api/v1/media/*)")
    except Exception:
        _LOGGER.exception("Failed to register Media Zones API")

    # Register Reminders API (waste + birthdays, v3.2.0)
    try:
        from copilot_core.api.v1.reminders import reminders_bp, init_reminders_api
        if services:
            init_reminders_api(
                services.get("waste_service"),
                services.get("birthday_service"),
            )
        app.register_blueprint(reminders_bp)
        _LOGGER.info("Registered Reminders API (/api/v1/waste/* + /api/v1/birthday/*)")
    except Exception:
        _LOGGER.exception("Failed to register Reminders API")

    # Register Haushalt Dashboard API (v3.2.2)
    try:
        from copilot_core.api.v1.haushalt import haushalt_bp
        app.register_blueprint(haushalt_bp)
        _LOGGER.info("Registered Haushalt API (/api/v1/haushalt/*)")
    except Exception:
        _LOGGER.exception("Failed to register Haushalt API")

    # Register Entity Assignment Suggestions API (v3.2.2)
    try:
        from copilot_core.api.v1.entity_assignment import entity_assignment_bp
        app.register_blueprint(entity_assignment_bp)
        _LOGGER.info("Registered Entity Assignment API (/api/v1/entity-assignment/*)")
    except Exception:
        _LOGGER.exception("Failed to register Entity Assignment API")

    # Register Presence Tracking API (v3.3.0)
    try:
        from copilot_core.api.v1.presence import presence_bp
        app.register_blueprint(presence_bp)
        _LOGGER.info("Registered Presence API (/api/v1/presence/*)")
    except Exception:
        _LOGGER.exception("Failed to register Presence API")

    # Register Scene Management API (v3.4.0)
    try:
        from copilot_core.api.v1.scenes import scenes_bp
        app.register_blueprint(scenes_bp)
        _LOGGER.info("Registered Scenes API (/api/v1/scenes/*)")
    except Exception:
        _LOGGER.exception("Failed to register Scenes API")

    # Register Scene Pattern Extraction API (v7.11.0)
    try:
        from copilot_core.api.v1.scene_patterns import scene_patterns_bp
        app.register_blueprint(scene_patterns_bp)
        _LOGGER.info("Registered Scene Patterns API (/api/v1/scenes/patterns/*)")
    except Exception:
        _LOGGER.exception("Failed to register Scene Patterns API")

    # Register Routine Pattern Extraction API (v7.11.0)
    try:
        from copilot_core.api.v1.routine_patterns import routine_patterns_bp
        app.register_blueprint(routine_patterns_bp)
        _LOGGER.info("Registered Routine Patterns API (/api/v1/routines/*)")
    except Exception:
        _LOGGER.exception("Failed to register Routine Patterns API")

    # Register Push Notifications API (v7.12.0)
    try:
        from copilot_core.api.v1.push_notifications import push_notifications_bp
        app.register_blueprint(push_notifications_bp)
        _LOGGER.info("Registered Push Notifications API (/api/v1/notifications/*)")
    except Exception:
        _LOGGER.exception("Failed to register Push Notifications API")

    # Register System Status API (v7.12.0)
    try:
        from copilot_core.api.v1.system_status import system_status_bp
        app.register_blueprint(system_status_bp)
        _LOGGER.info("Registered System Status API (/api/v1/system/*)")
    except Exception:
        _LOGGER.exception("Failed to register System Status API")

    # Register Entity Management API (v7.13.0)
    try:
        from copilot_core.api.v1.entities import entities_bp
        app.register_blueprint(entities_bp)
        _LOGGER.info("Registered Entity Management API (/api/v1/entities/*)")
    except Exception:
        _LOGGER.exception("Failed to register Entity Management API")

    # Register Automation Webhook API (v7.13.0)
    try:
        from copilot_core.api.v1.automation_webhook import automation_webhook_bp
        app.register_blueprint(automation_webhook_bp)
        _LOGGER.info("Registered Automation Webhook API (/api/v1/automation/*)")
    except Exception:
        _LOGGER.exception("Failed to register Automation Webhook API")

    # Register Service Calls API (v7.14.0)
    try:
        from copilot_core.api.v1.service_calls import services_bp
        app.register_blueprint(services_bp)
        _LOGGER.info("Registered Service Calls API (/api/v1/services/*)")
    except Exception:
        _LOGGER.exception("Failed to register Service Calls API")

    # Register Sensors API (v7.14.0)
    try:
        from copilot_core.api.v1.sensors import sensors_bp
        app.register_blueprint(sensors_bp)
        _LOGGER.info("Registered Sensors API (/api/v1/sensors/*)")
    except Exception:
        _LOGGER.exception("Failed to register Sensors API")

    # Register Lights API (v7.15.0)
    try:
        from copilot_core.api.v1.lights import lights_bp
        app.register_blueprint(lights_bp)
        _LOGGER.info("Registered Lights API (/api/v1/lights/*)")
    except Exception:
        _LOGGER.exception("Failed to register Lights API")

    # Register Climate API (v7.15.0)
    try:
        from copilot_core.api.v1.climate import climate_bp
        app.register_blueprint(climate_bp)
        _LOGGER.info("Registered Climate API (/api/v1/climate/*)")
    except Exception:
        _LOGGER.exception("Failed to register Climate API")

    # Register Switches API (v7.15.0)
    try:
        from copilot_core.api.v1.switches import switches_bp
        app.register_blueprint(switches_bp)
        _LOGGER.info("Registered Switches API (/api/v1/switches/*)")
    except Exception:
        _LOGGER.exception("Failed to register Switches API")

    # Register Media Players API (v7.16.0)
    try:
        from copilot_core.api.v1.media_players import media_bp
        app.register_blueprint(media_bp)
        _LOGGER.info("Registered Media Players API (/api/v1/media/*)")
    except Exception:
        _LOGGER.exception("Failed to register Media Players API")

    # Register Groups API (v7.16.0)
    try:
        from copilot_core.api.v1.groups import groups_bp
        app.register_blueprint(groups_bp)
        _LOGGER.info("Registered Groups API (/api/v1/groups/*)")
    except Exception:
        _LOGGER.exception("Failed to register Groups API")

    # Register Input Select API (v7.17.0)
    try:
        from copilot_core.api.v1.input_select import input_select_bp
        app.register_blueprint(input_select_bp)
        _LOGGER.info("Registered Input Select API (/api/v1/input_select/*)")
    except Exception:
        _LOGGER.exception("Failed to register Input Select API")

    # Register Scenes v2 API (v7.17.0)
    try:
        from copilot_core.api.v1.scenes_v2 import scenes_v2_bp
        app.register_blueprint(scenes_v2_bp)
        _LOGGER.info("Registered Scenes v2 API (/api/v1/scenes/v2/*)")
    except Exception:
        _LOGGER.exception("Failed to register Scenes v2 API")

    # Register Covers API (v7.18.0)
    try:
        from copilot_core.api.v1.covers import covers_bp
        app.register_blueprint(covers_bp)
        _LOGGER.info("Registered Covers API (/api/v1/covers/*)")
    except Exception:
        _LOGGER.exception("Failed to register Covers API")

    # Register Fans API (v7.18.0)
    try:
        from copilot_core.api.v1.fans import fans_bp
        app.register_blueprint(fans_bp)
        _LOGGER.info("Registered Fans API (/api/v1/fans/*)")
    except Exception:
        _LOGGER.exception("Failed to register Fans API")

    # Register Webhooks API (v7.19.0)
    try:
        from copilot_core.api.v1.webhooks import webhooks_bp
        app.register_blueprint(webhooks_bp)
        _LOGGER.info("Registered Webhooks API (/api/v1/webhooks/*)")
    except Exception:
        _LOGGER.exception("Failed to register Webhooks API")

    # Register Summary API (v7.19.0)
    try:
        from copilot_core.api.v1.summary import summary_bp
        app.register_blueprint(summary_bp)
        _LOGGER.info("Registered Summary API (/api/v1/summary/*)")
    except Exception:
        _LOGGER.exception("Failed to register Summary API")

    # Register History API (v7.20.0)
    try:
        from copilot_core.api.v1.history import history_bp
        app.register_blueprint(history_bp)
        _LOGGER.info("Registered History API (/api/v1/history/*)")
    except Exception:
        _LOGGER.exception("Failed to register History API")

    # Register Locks API (v7.21.0)
    try:
        from copilot_core.api.v1.locks import locks_bp
        app.register_blueprint(locks_bp)
        _LOGGER.info("Registered Locks API (/api/v1/locks/*)")
    except Exception:
        _LOGGER.exception("Failed to register Locks API")

    # Register Alerts API (v7.22.0)
    try:
        from copilot_core.api.v1.alerts import alerts_bp
        app.register_blueprint(alerts_bp)
        _LOGGER.info("Registered Alerts API (/api/v1/alerts/*)")
    except Exception:
        _LOGGER.exception("Failed to register Alerts API")

    # Register Weather API (v7.23.0)
    try:
        from copilot_core.api.v1.weather import weather_bp
        app.register_blueprint(weather_bp)
        _LOGGER.info("Registered Weather API (/api/v1/weather/*)")
    except Exception:
        _LOGGER.exception("Failed to register Weather API")

    # Register HomeKit Bridge API (v3.4.0)
    try:
        from copilot_core.api.v1.homekit import homekit_bp
        app.register_blueprint(homekit_bp)
        _LOGGER.info("Registered HomeKit API (/api/v1/homekit/*)")
    except Exception:
        _LOGGER.exception("Failed to register HomeKit API")

    # Register Calendar API (v3.5.0)
    try:
        from copilot_core.api.v1.calendar import calendar_bp
        app.register_blueprint(calendar_bp)
        _LOGGER.info("Registered Calendar API (/api/v1/calendar/*)")
    except Exception:
        _LOGGER.exception("Failed to register Calendar API")

    # Register Shopping List & Reminders API (v3.5.0)
    try:
        from copilot_core.api.v1.shopping_list import shopping_list_bp
        app.register_blueprint(shopping_list_bp)
        _LOGGER.info("Registered Shopping List & Reminders API (/api/v1/shopping-list/*)")
    except Exception:
        _LOGGER.exception("Failed to register Shopping List & Reminders API")


    # Register Input Number API (v7.25.0)
    try:
        from copilot_core.api.v1.input_number import input_number_bp
        app.register_blueprint(input_number_bp)
        _LOGGER.info("Registered Input Number API (/api/v1/input_number/*)")
    except Exception:
        _LOGGER.exception("Failed to register Input Number API")

    # Register Zones API (v7.25.0)
    try:
        from copilot_core.api.v1.zones import zones_bp
        app.register_blueprint(zones_bp)
        _LOGGER.info("Registered Zones API (/api/v1/zones/*)")
    except Exception:
        _LOGGER.exception("Failed to register Zones API")

    # Register Config Management API (v7.28.0)
    try:
        from copilot_core.api.v1.config_management import config_bp
        app.register_blueprint(config_bp)
        _LOGGER.info("Registered Config Management API (/api/v1/config/*)")
    except Exception:
        _LOGGER.exception("Failed to register Config Management API")

    # Register Templates API (v7.28.0)
    try:
        from copilot_core.api.v1.templates import templates_bp
        app.register_blueprint(templates_bp)
        _LOGGER.info("Registered Templates API (/api/v1/templates/*)")
    except Exception:
        _LOGGER.exception("Failed to register Templates API")

    # Register Logbook API (v7.29.0)
    try:
        from copilot_core.api.v1.logbook import logbook_bp
        app.register_blueprint(logbook_bp)
        _LOGGER.info("Registered Logbook API (/api/v1/logbook/*)")
    except Exception:
        _LOGGER.exception("Failed to register Logbook API")

    # Register Repairs API (v7.30.0)
    try:
        from copilot_core.api.v1.repairs import repairs_bp
        app.register_blueprint(repairs_bp)
        _LOGGER.info("Registered Repairs API (/api/v1/repairs/*)")
    except Exception:
        _LOGGER.exception("Failed to register Repairs API")

    # Register System Health API (v7.30.0)
    try:
        from copilot_core.api.v1.system_health import system_health_bp
        app.register_blueprint(system_health_bp)
        _LOGGER.info("Registered System Health API (/api/v1/system_health/*)")
    except Exception:
        _LOGGER.exception("Failed to register System Health API")

    # Register Energy API (v7.31.0)
    try:
        from copilot_core.api.v1.energy import energy_bp
        app.register_blueprint(energy_bp)
        _LOGGER.info("Registered Energy API (/api/v1/energy/*)")
    except:
        pass

    # Register Persons API (v7.31.0)
    try:
        from copilot_core.api.v1.persons import persons_bp
        app.register_blueprint(persons_bp)
        _LOGGER.info("Registered Persons API (/api/v1/persons/*)")
    except:
        pass

    # Register Tags API (v7.32)
    try:
        from copilot_core.api.v1.tags import tags_bp
        app.register_blueprint(tags_bp)
    except: pass

    # Register Devices API (v7.33)
    try:
        from copilot_core.api.v1.devices import devices_bp
        app.register_blueprint(devices_bp)
    except: pass

    # Register Areas API (v7.34)
    try:
        from copilot_core.api.v1.areas import areas_bp
        app.register_blueprint(areas_bp)
    except: pass

    # Register Issues API (v7.35)
    try:
        from copilot_core.api.v1.issues import issues_bp
        app.register_blueprint(issues_bp)
    except: pass

    # Register Versions API (v7.36)
    try:
        from copilot_core.api.v1.versions import versions_bp
        app.register_blueprint(versions_bp)
    except: pass

    # Register Diagnostics API (v7.36)
    try:
        from copilot_core.api.v1.diagnostics import diagnostics_bp
        app.register_blueprint(diagnostics_bp)
    except: pass
    try:
        from copilot_core.api.v1.helpers import helpers_bp
        app.register_blueprint(helpers_bp)
    except: pass
    try:
        from copilot_core.api.v1.oauth import oauth_bp
        app.register_blueprint(oauth_bp)
    except: pass
    try:
        from copilot_core.api.v1.auth import auth_bp
        app.register_blueprint(auth_bp)
    except: pass
    try:
        from copilot_core.api.v1.info import info_bp
        app.register_blueprint(info_bp)
    except: pass
    try:
        from copilot_core.api.v1.bluetooth import bluetooth_bp
        app.register_blueprint(bluetooth_bp)
    except: pass
    try:
        from copilot_core.api.v1.usb import usb_bp
        app.register_blueprint(usb_bp)
    except: pass
    try:
        from copilot_core.api.v1.network import network_bp
        app.register_blueprint(network_bp)
    except: pass
    try:
        from copilot_core.api.v1.core import core_bp
        app.register_blueprint(core_bp)
    except: pass
    try:
        from copilot_core.api.v1.front import front_bp
        app.register_blueprint(front_bp)
    except: pass
    try:
        from copilot_core.api.v1.panel import panel_bp
        app.register_blueprint(panel_bp)
    except: pass
    try:
        from copilot_core.api.v1.logbook2 import logbook2_bp
        app.register_blueprint(logbook2_bp)
    except: pass
    try:
        from copilot_core.api.v1.raspberry import raspberry_bp
        app.register_blueprint(raspberry_bp)
    except: pass
    try:
        from copilot_core.api.v1.stream import stream_bp
        app.register_blueprint(stream_bp)
    except: pass
    try:
        from copilot_core.api.v1.counter import counter_bp
        app.register_blueprint(counter_bp)
    except: pass
    try:
        from copilot_core.api.v1.timer import timer_bp
        app.register_blueprint(timer_bp)
    except: pass
    try:
        from copilot_core.api.v1.binary_sensor import binary_bp
        app.register_blueprint(binary_bp)
    except: pass
    try:
        from copilot_core.api.v1.calendar import calendar_bp
        app.register_blueprint(calendar_bp)
    except: pass
    try:
        from copilot_core.api.v1.camera import camera_bp
        app.register_blueprint(camera_bp)
    except: pass
    try:
        from copilot_core.api.v1.vacuum import vacuum_bp
        app.register_blueprint(vacuum_bp)
    except: pass
    try:
        from copilot_core.api.v1.light import light_bp
        app.register_blueprint(light_bp)
    except: pass
    try:
        from copilot_core.api.v1.switch_v2 import switch_bp
        app.register_blueprint(switch_bp)
    except: pass
    try:
        from copilot_core.api.v1.wakeword import wakeword_bp
        app.register_blueprint(wakeword_bp)
    except: pass
    try:
        from copilot_core.api.v1.tts import tts_bp
        app.register_blueprint(tts_bp)
    except: pass
    try:
        from copilot_core.api.v1.stt import stt_bp
        app.register_blueprint(stt_bp)
    except: pass
    try:
        from copilot_core.api.v1.tts_v2 import tts2_bp
        app.register_blueprint(tts2_bp)
    except: pass
    try:
        from copilot_core.api.v1.conversation import conversation_bp
        app.register_blueprint(conversation_bp)
    except: pass
    try:
        from copilot_core.api.v1.intent import intent_bp
        app.register_blueprint(intent_bp)
    except: pass
    try:
        from copilot_core.api.v1.selector import selector_bp
        app.register_blueprint(selector_bp)
    except: pass
    try:
        from copilot_core.api.v1.update import update_bp
        app.register_blueprint(update_bp)
    except: pass
    try:
        from copilot_core.api.v1.number import number_bp
        app.register_blueprint(number_bp)
    except: pass
    try:
        from copilot_core.api.v1.button import button_bp
        app.register_blueprint(button_bp)
    except: pass
    try:
        from copilot_core.api.v1.image import image_bp
        app.register_blueprint(image_bp)
    except: pass
    try:
        from copilot_core.api.v1.homekit import homekit_bp
        app.register_blueprint(homekit_bp)
    except: pass
    try:
        from copilot_core.api.v1.sonos import sonos_bp
        app.register_blueprint(sonos_bp)
    except: pass
    try:
        from copilot_core.api.v1.plex import plex_bp
        app.register_blueprint(plex_bp)
    except: pass
    try:
        from copilot_core.api.v1.spotify import spotify_bp
        app.register_blueprint(spotify_bp)
    except: pass
    try:
        from copilot_core.api.v1.gtts import gtts_bp
        app.register_blueprint(gtts_bp)
    except: pass
    try:
        from copilot_core.api.v1.alexa import alexa_bp
        app.register_blueprint(alexa_bp)
    except: pass
    try:
        from copilot_core.api.v1.knx import knx_bp
        app.register_blueprint(knx_bp)
    except: pass
    try:
        from copilot_core.api.v1.zwave import zwave_bp
        app.register_blueprint(zwave_bp)
    except: pass
    try:
        from copilot_core.api.v1.zigbee import zigbee_bp
        app.register_blueprint(zigbee_bp)
    except: pass
    try:
        from copilot_core.api.v1.mqtt import mqtt_bp
        app.register_blueprint(mqtt_bp)
    except: pass
    try:
        from copilot_core.api.v1.backup import backup_bp
        app.register_blueprint(backup_bp)
    except: pass
    try:
        from copilot_core.api.v1.restore import restore_bp
        app.register_blueprint(restore_bp)
    except: pass
    try:
        from copilot_core.api.v1.shop import shop_bp
        app.register_blueprint(shop_bp)
    except: pass
    try:
        from copilot_core.api.v1.shopping import shopping_bp
        app.register_blueprint(shopping_bp)
    except: pass
    try:
        from copilot_core.api.v1.todo import todo_bp
        app.register_blueprint(todo_bp)
    except: pass
    try:
        from copilot_core.api.v1.humidifier import humidifier_bp
        app.register_blueprint(humidifier_bp)
    except: pass
    try:
        from copilot_core.api.v1.water_heater import water_bp
        app.register_blueprint(water_bp)
    except: pass
    try:
        from copilot_core.api.v1.airquality import airquality_bp
        app.register_blueprint(airquality_bp)
    except: pass
    try:
        from copilot_core.api.v1.binarysensor import binarysensor_bp
        app.register_blueprint(binarysensor_bp)
    except: pass
    try:
        from copilot_core.api.v1.siren import siren_bp
        app.register_blueprint(siren_bp)
    except: pass
    try:
        from copilot_core.api.v1.lightfull import lightfull_bp
        app.register_blueprint(lightfull_bp)
    except: pass
    try:
        from copilot_core.api.v1.throttle import throttle_bp
        app.register_blueprint(throttle_bp)
    except: pass
    try:
        from copilot_core.api.v1.ratelimit import ratelimit_bp
        app.register_blueprint(ratelimit_bp)
    except: pass
    try:
        from copilot_core.api.v1.cache import cache_bp
        app.register_blueprint(cache_bp)
    except: pass
    try:
        from copilot_core.api.v1.debug import debug_bp
        app.register_blueprint(debug_bp)
    except: pass
    try:
        from copilot_core.api.v1.metrics import metrics_bp
        app.register_blueprint(metrics_bp)
    except: pass
    try:
        from copilot_core.api.v1.health2 import health_bp
        app.register_blueprint(health_bp)
    except: pass
    try:
        from copilot_core.api.v1.status2 import status_bp
        app.register_blueprint(status_bp)
    except: pass
    try:
        from copilot_core.api.v1.version2 import version2_bp
        app.register_blueprint(version2_bp)
    except: pass
    try:
        from copilot_core.api.v1.feature import feature_bp
        app.register_blueprint(feature_bp)
    except: pass
    try:
        from copilot_core.api.v1.test import test_bp
        app.register_blueprint(test_bp)
    except: pass
    try:
        from copilot_core.api.v1.user import user_bp
        app.register_blueprint(user_bp)
    except: pass
    try:
        from copilot_core.api.v1.role import role_bp
        app.register_blueprint(role_bp)
    except: pass
    try:
        from copilot_core.api.v1.permission import permission_bp
        app.register_blueprint(permission_bp)
    except: pass
    try:
        from copilot_core.api.v1.session import session_bp
        app.register_blueprint(session_bp)
    except: pass
    try:
        from copilot_core.api.v1.authtoken import authtoken_bp
        app.register_blueprint(authtoken_bp)
    except: pass
    try:
        from copilot_core.api.v1.auditlog import auditlog_bp
        app.register_blueprint(auditlog_bp)
    except: pass
    try:
        from copilot_core.api.v1.auditevent import auditevent_bp
        app.register_blueprint(auditevent_bp)
    except: pass
    try:
        from copilot_core.api.v1.report import report_bp
        app.register_blueprint(report_bp)
    except: pass
    try:
        from copilot_core.api.v1.export import export_bp
        app.register_blueprint(export_bp)
    except: pass
    try:
        from copilot_core.api.v1.import import import_bp
        app.register_blueprint(import_bp)
    except: pass
    try:
        from copilot_core.api.v1.file import file_bp
        app.register_blueprint(file_bp)
    except: pass
    try:
        from copilot_core.api.v1.directory import directory_bp
        app.register_blueprint(directory_bp)
    except: pass
    try:
        from copilot_core.api.v1.storage import storage_bp
        app.register_blueprint(storage_bp)
    except: pass
    try:
        from copilot_core.api.v1.upload import upload_bp
        app.register_blueprint(upload_bp)
    except: pass
    try:
        from copilot_core.api.v1.download import download_bp
        app.register_blueprint(download_bp)
    except: pass
    try:
        from copilot_core.api.v1.media2 import media2_bp
        app.register_blueprint(media2_bp)
    except: pass
    try:
        from copilot_core.api.v1.document import document_bp
        app.register_blueprint(document_bp)
    except: pass
    try:
        from copilot_core.api.v1.archive import archive_bp
        app.register_blueprint(archive_bp)
    except: pass
    try:
        from copilot_core.api.v1.encrypt import encrypt_bp
        app.register_blueprint(encrypt_bp)
    except: pass
    try:
        from copilot_core.api.v1.decrypt import decrypt_bp
        app.register_blueprint(decrypt_bp)
    except: pass
    try:
        from copilot_core.api.v1.certificate import cert_bp
        app.register_blueprint(cert_bp)
    except: pass
    try:
        from copilot_core.api.v1.vpn import vpn_bp
        app.register_blueprint(vpn_bp)
    except: pass
    try:
        from copilot_core.api.v1.firewall import firewall_bp
        app.register_blueprint(firewall_bp)
    except: pass
    try:
        from copilot_core.api.v1.proxy import proxy_bp
        app.register_blueprint(proxy_bp)
    except: pass
    try:
        from copilot_core.api.v1.dns import dns_bp
        app.register_blueprint(dns_bp)
    except: pass
    try:
        from copilot_core.api.v1.netint import netint_bp
        app.register_blueprint(netint_bp)
    except: pass
    try:
        from copilot_core.api.v1.interface import interface_bp
        app.register_blueprint(interface_bp)
    except: pass
    try:
        from copilot_core.api.v1.subnet import subnet_bp
        app.register_blueprint(subnet_bp)
    except: pass
    try:
        from copilot_core.api.v1.gateway import gateway_bp
        app.register_blueprint(gateway_bp)
    except: pass
    try:
        from copilot_core.api.v1.route import route_bp
        app.register_blueprint(route_bp)
    except: pass
    try:
        from copilot_core.api.v1.ifaceconfig import ifaceconfig_bp
        app.register_blueprint(ifaceconfig_bp)
    except: pass
    try:
        from copilot_core.api.v1.dhcp import dhcp_bp
        app.register_blueprint(dhcp_bp)
    except: pass
    try:
        from copilot_core.api.v1.ipv4 import ipv4_bp
        app.register_blueprint(ipv4_bp)
    except: pass
    try:
        from copilot_core.api.v1.ipv6 import ipv6_bp
        app.register_blueprint(ipv6_bp)
    except: pass
    try:
        from copilot_core.api.v1.mac import mac_bp
        app.register_blueprint(mac_bp)
    except: pass
    try:
        from copilot_core.api.v1.snmp import snmp_bp
        app.register_blueprint(snmp_bp)
    except: pass
    try:
        from copilot_core.api.v1.smtp import smtp_bp
        app.register_blueprint(smtp_bp)
    except: pass
    try:
        from copilot_core.api.v1.imap import imap_bp
        app.register_blueprint(imap_bp)
    except: pass
    try:
        from copilot_core.api.v1.pop3 import pop3_bp
        app.register_blueprint(pop3_bp)
    except: pass
    try:
        from copilot_core.api.v1.ftp import ftp_bp
        app.register_blueprint(ftp_bp)
    except: pass
    try:
        from copilot_core.api.v1.ssh import ssh_bp
        app.register_blueprint(ssh_bp)
    except: pass
    try:
        from copilot_core.api.v1.telnet import telnet_bp
        app.register_blueprint(telnet_bp)
    except: pass
    try:
        from copilot_core.api.v1.rdp import rdp_bp
        app.register_blueprint(rdp_bp)
    except: pass
    try:
        from copilot_core.api.v1.vnc import vnc_bp
        app.register_blueprint(vnc_bp)
    except: pass
    try:
        from copilot_core.api.v1.rdp2 import rdp2_bp
        app.register_blueprint(rdp2_bp)
    except: pass
    try:
        from copilot_core.api.v1.rdp3 import rdp3_bp
        app.register_blueprint(rdp3_bp)
    except: pass
    try:
        from copilot_core.api.v1.ssh2 import ssh2_bp
        app.register_blueprint(ssh2_bp)
    except: pass
    try:
        from copilot_core.api.v1.telnet2 import telnet2_bp
        app.register_blueprint(telnet2_bp)
    except: pass
    try:
        from copilot_core.api.v1.vnc2 import vnc2_bp
        app.register_blueprint(vnc2_bp)
    except: pass
    try:
        from copilot_core.api.v1.tty import tty_bp
        app.register_blueprint(tty_bp)
    except: pass
    try:
        from copilot_core.api.v1.kvm import kvm_bp
        app.register_blueprint(kvm_bp)
    except: pass
    try:
        from copilot_core.api.v1.console import console_bp
        app.register_blueprint(console_bp)
    except: pass
    try:
        from copilot_core.api.v1.serial import serial_bp
        app.register_blueprint(serial_bp)
    except: pass
    try:
        from copilot_core.api.v1.usbip import usbip_bp
        app.register_blueprint(usbip_bp)
    except: pass
    try:
        from copilot_core.api.v1.netboot import netboot_bp
        app.register_blueprint(netboot_bp)
    except: pass
    try:
        from copilot_core.api.v1.pxe import pxe_bp
        app.register_blueprint(pxe_bp)
    except: pass
    try:
        from copilot_core.api.v1.ipxe import ipxe_bp
        app.register_blueprint(ipxe_bp)
    except: pass
    try:
        from copilot_core.api.v1.uefi import uefi_bp
        app.register_blueprint(uefi_bp)
    except: pass
    try:
        from copilot_core.api.v1.bios import bios_bp
        app.register_blueprint(bios_bp)
    except: pass
    try:
        from copilot_core.api.v1.firmware import firmware_bp
        app.register_blueprint(firmware_bp)
    except: pass
    try:
        from copilot_core.api.v1.memory import memory_bp
        app.register_blueprint(memory_bp)
    except: pass
    try:
        from copilot_core.api.v1.cpu import cpu_bp
        app.register_blueprint(cpu_bp)
    except: pass
    try:
        from copilot_core.api.v1.gpu import gpu_bp
        app.register_blueprint(gpu_bp)
    except: pass
    try:
        from copilot_core.api.v1.disk import disk_bp
        app.register_blueprint(disk_bp)
    except: pass
    try:
        from copilot_core.api.v1.raid import raid_bp
        app.register_blueprint(raid_bp)
    except: pass
    try:
        from copilot_core.api.v1.thermal import thermal_bp
        app.register_blueprint(thermal_bp)
    except: pass
    try:
        from copilot_core.api.v1.power import power_bp
        app.register_blueprint(power_bp)
    except: pass
    try:
        from copilot_core.api.v1.battery import battery_bp
        app.register_blueprint(battery_bp)
    except: pass
    try:
        from copilot_core.api.v1.ups import ups_bp
        app.register_blueprint(ups_bp)
    except: pass
    try:
        from copilot_core.api.v1.fan2 import fan_bp
        app.register_blueprint(fan_bp)
    except: pass
    try:
        from copilot_core.api.v1.sound import sound_bp
        app.register_blueprint(sound_bp)
    except: pass
    try:
        from copilot_core.api.v1.mic import mic_bp
        app.register_blueprint(mic_bp)
    except: pass
    try:
        from copilot_core.api.v1.speaker import speaker_bp
        app.register_blueprint(speaker_bp)
    except: pass
    try:
        from copilot_core.api.v1.audio import audio_bp
        app.register_blueprint(audio_bp)
    except: pass
    try:
        from copilot_core.api.v1.video import video_bp
        app.register_blueprint(video_bp)
    except: pass
    try:
        from copilot_core.api.v1.display import display_bp
        app.register_blueprint(display_bp)
    except: pass
    try:
        from copilot_core.api.v1.touchscreen import touchscreen_bp
        app.register_blueprint(touchscreen_bp)
    except: pass
    try:
        from copilot_core.api.v1.resolution import resolution_bp
        app.register_blueprint(resolution_bp)
    except: pass
    try:
        from copilot_core.api.v1.brightness import brightness_bp
        app.register_blueprint(brightness_bp)
    except: pass
    try:
        from copilot_core.api.v1.contrast import contrast_bp
        app.register_blueprint(contrast_bp)
    except: pass
    try:
        from copilot_core.api.v1.aspect import aspect_bp
        app.register_blueprint(aspect_bp)
    except: pass
    try:
        from copilot_core.api.v1.gamma import gamma_bp
        app.register_blueprint(gamma_bp)
    except: pass
    try:
        from copilot_core.api.v1.hue import hue_bp
        app.register_blueprint(hue_bp)
    except: pass
    try:
        from copilot_core.api.v1.saturation import saturation_bp
        app.register_blueprint(saturation_bp)
    except: pass
    try:
        from copilot_core.api.v1.contrast2 import contrast2_bp
        app.register_blueprint(contrast2_bp)
    except: pass
    try:
        from copilot_core.api.v1.scan import scan_bp
        app.register_blueprint(scan_bp)
    except: pass
    try:
        from copilot_core.api.v1.ocr import ocr_bp
        app.register_blueprint(ocr_bp)
    except: pass
    try:
        from copilot_core.api.v1.printer import printer_bp
        app.register_blueprint(printer_bp)
    except: pass
    try:
        from copilot_core.api.v1.scanner import scanner_bp
        app.register_blueprint(scanner_bp)
    except: pass
    try:
        from copilot_core.api.v1.copier import copier_bp
        app.register_blueprint(copier_bp)
    except: pass
    try:
        from copilot_core.api.v1.fax import fax_bp
        app.register_blueprint(fax_bp)
    except: pass
    try:
        from copilot_core.api.v1.modem import modem_bp
        app.register_blueprint(modem_bp)
    except: pass
    try:
        from copilot_core.api.v1.isdn import isdn_bp
        app.register_blueprint(isdn_bp)
    except: pass
    try:
        from copilot_core.api.v1.dsl import dsl_bp
        app.register_blueprint(dsl_bp)
    except: pass
    try:
        from copilot_core.api.v1.pon import pon_bp
        app.register_blueprint(pon_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifi import wifi_bp
        app.register_blueprint(wifi_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifi5g import wifi5g_bp
        app.register_blueprint(wifi5g_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifi6 import wifi6_bp
        app.register_blueprint(wifi6_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifi7 import wifi7_bp
        app.register_blueprint(wifi7_bp)
    except: pass
    try:
        from copilot_core.api.v1.ethernet import eth_bp
        app.register_blueprint(eth_bp)
    except: pass
    try:
        from copilot_core.api.v1.cellular import cellular_bp
        app.register_blueprint(cellular_bp)
    except: pass
    try:
        from copilot_core.api.v1.fourg import fourg_bp
        app.register_blueprint(fourg_bp)
    except: pass
    try:
        from copilot_core.api.v1.fiveg import fiveg_bp
        app.register_blueprint(fiveg_bp)
    except: pass
    try:
        from copilot_core.api.v1.lte import lte_bp
        app.register_blueprint(lte_bp)
    except: pass
    try:
        from copilot_core.api.v1.nbiot import nbiot_bp
        app.register_blueprint(nbiot_bp)
    except: pass
    try:
        from copilot_core.api.v1.lora import lora_bp
        app.register_blueprint(lora_bp)
    except: pass
    try:
        from copilot_core.api.v1.sigfox import sigfox_bp
        app.register_blueprint(sigfox_bp)
    except: pass
    try:
        from copilot_core.api.v1.zigbee2mqtt import zigbee2mqtt_bp
        app.register_blueprint(zigbee2mqtt_bp)
    except: pass
    try:
        from copilot_core.api.v1.zwavejs import zwavejs_bp
        app.register_blueprint(zwavejs_bp)
    except: pass
    try:
        from copilot_core.api.v1.matter import matter_bp
        app.register_blueprint(matter_bp)
    except: pass
    try:
        from copilot_core.api.v1.thread import thread_bp
        app.register_blueprint(thread_bp)
    except: pass
    try:
        from copilot_core.api.v1.ble import ble_bp
        app.register_blueprint(ble_bp)
    except: pass
    try:
        from copilot_core.api.v1.nfc import nfc_bp
        app.register_blueprint(nfc_bp)
    except: pass
    try:
        from copilot_core.api.v1.rfid import rfid_bp
        app.register_blueprint(rfid_bp)
    except: pass
    try:
        from copilot_core.api.v1.uwb import uwb_bp
        app.register_blueprint(uwb_bp)
    except: pass
    try:
        from copilot_core.api.v1.zigbee3 import zigbee3_bp
        app.register_blueprint(zigbee3_bp)
    except: pass
    try:
        from copilot_core.api.v1.matter12 import matter12_bp
        app.register_blueprint(matter12_bp)
    except: pass
    try:
        from copilot_core.api.v1.thread12 import thread12_bp
        app.register_blueprint(thread12_bp)
    except: pass
    try:
        from copilot_core.api.v1.homekit2 import homekit2_bp
        app.register_blueprint(homekit2_bp)
    except: pass
    try:
        from copilot_core.api.v1.applehome import applehome_bp
        app.register_blueprint(applehome_bp)
    except: pass
    try:
        from copilot_core.api.v1.matter13 import matter13_bp
        app.register_blueprint(matter13_bp)
    except: pass
    try:
        from copilot_core.api.v1.matter14 import matter14_bp
        app.register_blueprint(matter14_bp)
    except: pass
    try:
        from copilot_core.api.v1.thread13 import thread13_bp
        app.register_blueprint(thread13_bp)
    except: pass
    try:
        from copilot_core.api.v1.thread14 import thread14_bp
        app.register_blueprint(thread14_bp)
    except: pass
    try:
        from copilot_core.api.v1.motel import motel_bp
        app.register_blueprint(motel_bp)
    except: pass
    try:
        from copilot_core.api.v1.wec import wec_bp
        app.register_blueprint(wec_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifiaware import wifiaware_bp
        app.register_blueprint(wifiaware_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifidirect import wifidirect_bp
        app.register_blueprint(wifidirect_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifip2p import wifip2p_bp
        app.register_blueprint(wifip2p_bp)
    except: pass
    try:
        from copilot_core.api.v1.wifitdls import wifitdls_bp
        app.register_blueprint(wifitdls_bp)
    except: pass
    try:
        from copilot_core.api.v1.usb4 import usb4_bp
        app.register_blueprint(usb4_bp)
    except: pass
    try:
        from copilot_core.api.v1.usb3 import usb3_bp
        app.register_blueprint(usb3_bp)
    except: pass
    try:
        from copilot_core.api.v1.thunderbolt import thunderbolt_bp
        app.register_blueprint(thunderbolt_bp)
    except: pass
    try:
        from copilot_core.api.v1.pcie import pcie_bp
        app.register_blueprint(pcie_bp)
    except: pass
    try:
        from copilot_core.api.v1.sata import sata_bp
        app.register_blueprint(sata_bp)
    except: pass
    try:
        from copilot_core.api.v1.nvme import nvme_bp
        app.register_blueprint(nvme_bp)
    except: pass
    try:
        from copilot_core.api.v1.sas import sas_bp
        app.register_blueprint(sas_bp)
    except: pass
    try:
        from copilot_core.api.v1.emmc import emmc_bp
        app.register_blueprint(emmc_bp)
    except: pass
    try:
        from copilot_core.api.v1.sdcard import sdcard_bp
        app.register_blueprint(sdcard_bp)
    except: pass
    try:
        from copilot_core.api.v1.ufs import ufs_bp
        app.register_blueprint(ufs_bp)
    except: pass
    try:
        from copilot_core.api.v1.tpm import tpm_bp
        app.register_blueprint(tpm_bp)
    except: pass
    try:
        from copilot_core.api.v1.secboot import secboot_bp
        app.register_blueprint(secboot_bp)
    except: pass
    try:
        from copilot_core.api.v1.uefi import uefi_bp
        app.register_blueprint(uefi_bp)
    except: pass
    try:
        from copilot_core.api.v1.bios import bios_bp
        app.register_blueprint(bios_bp)
    except: pass
    try:
        from copilot_core.api.v1.intelme import intelme_bp
        app.register_blueprint(intelme_bp)
    except: pass
    try:
        from copilot_core.api.v1.amdpsp import amdpsp_bp
        app.register_blueprint(amdpsp_bp)
    except: pass
    try:
        from copilot_core.api.v1.trench import trench_bp
        app.register_blueprint(trench_bp)
    except: pass
    try:
        from copilot_core.api.v1.bootguard import bootguard_bp
        app.register_blueprint(bootguard_bp)
    except: pass
    try:
        from copilot_core.api.v1.drm import drm_bp
        app.register_blueprint(drm_bp)
    except: pass
    try:
        from copilot_core.api.v1.hdcp import hdcp_bp
        app.register_blueprint(hdcp_bp)
    except: pass
    try:
        from copilot_core.api.v1.widevine import widevine_bp
        app.register_blueprint(widevine_bp)
    except: pass
    try:
        from copilot_core.api.v1.playready import playready_bp
        app.register_blueprint(playready_bp)
    except: pass
    try:
        from copilot_core.api.v1.fairplay import fairplay_bp
        app.register_blueprint(fairplay_bp)
    except: pass
    try:
        from copilot_core.api.v1.eme import eme_bp
        app.register_blueprint(eme_bp)
    except: pass
    try:
        from copilot_core.api.v1.webrtc import webrtc_bp
        app.register_blueprint(webrtc_bp)
    except: pass
    try:
        from copilot_core.api.v1.sip import sip_bp
        app.register_blueprint(sip_bp)
    except: pass
    try:
        from copilot_core.api.v1.voip import voip_bp
        app.register_blueprint(voip_bp)
    except: pass
    try:
        from copilot_core.api.v1.rtp import rtp_bp
        app.register_blueprint(rtp_bp)
    except: pass
    try:
        from copilot_core.api.v1.rtsp import rtsp_bp
        app.register_blueprint(rtsp_bp)
    except: pass
    try:
        from copilot_core.api.v1.srt import srt_bp
        app.register_blueprint(srt_bp)
    except: pass
    try:
        from copilot_core.api.v1.hls import hls_bp
        app.register_blueprint(hls_bp)
    except: pass
    try:
        from copilot_core.api.v1.dash import dash_bp
        app.register_blueprint(dash_bp)
    except: pass
    try:
        from copilot_core.api.v1.ws import ws_bp
        app.register_blueprint(ws_bp)
    except: pass
    try:
        from copilot_core.api.v1.graphql import graphql_bp
        app.register_blueprint(graphql_bp)
    except: pass
    try:
        from copilot_core.api.v1.grpc import grpc_bp
        app.register_blueprint(grpc_bp)
    except: pass
    try:
        from copilot_core.api.v1.prometheus import prometheus_bp
        app.register_blueprint(prometheus_bp)
    except: pass
    try:
        from copilot_core.api.v1.grafana import grafana_bp
        app.register_blueprint(grafana_bp)
    except: pass
    try:
        from copilot_core.api.v1.influxdb import influxdb_bp
        app.register_blueprint(influxdb_bp)
    except: pass
    try:
        from copilot_core.api.v1.telegraf import telegraf_bp
        app.register_blueprint(telegraf_bp)
    except: pass
    try:
        from copilot_core.api.v1.timescaledb import timescaledb_bp
        app.register_blueprint(timescaledb_bp)
    except: pass
    try:
        from copilot_core.api.v1.opentelemetry import opentelemetry_bp
        app.register_blueprint(opentelemetry_bp)
    except: pass
    try:
        from copilot_core.api.v1.jaeger import jaeger_bp
        app.register_blueprint(jaeger_bp)
    except: pass
    try:
        from copilot_core.api.v1.zipkin import zipkin_bp
        app.register_blueprint(zipkin_bp)
    except: pass
    try:
        from copilot_core.api.v1.elk import elk_bp
        app.register_blueprint(elk_bp)
    except: pass
    try:
        from copilot_core.api.v1.splunk import splunk_bp
        app.register_blueprint(splunk_bp)
    except: pass
    try:
        from copilot_core.api.v1.graylog import graylog_bp
        app.register_blueprint(graylog_bp)
    except: pass
    try:
        from copilot_core.api.v1.loki import loki_bp
        app.register_blueprint(loki_bp)
    except: pass
    try:
        from copilot_core.api.v1.alertmanager import alertmanager_bp
        app.register_blueprint(alertmanager_bp)
    except: pass
    try:
        from copilot_core.api.v1.pushover import pushover_bp
        app.register_blueprint(pushover_bp)
    except: pass
    try:
        from copilot_core.api.v1.ntfy import ntfy_bp
        app.register_blueprint(ntfy_bp)
    except: pass
    try:
        from copilot_core.api.v1.matrix import matrix_bp
        app.register_blueprint(matrix_bp)
    except: pass
    try:
        from copilot_core.api.v1.element import element_bp
        app.register_blueprint(element_bp)
    except: pass
    try:
        from copilot_core.api.v1.synapse import synapse_bp
        app.register_blueprint(synapse_bp)
    except: pass
    try:
        from copilot_core.api.v1.dendrite import dendrite_bp
        app.register_blueprint(dendrite_bp)
    except: pass
    try:
        from copilot_core.api.v1.conduit import conduit_bp
        app.register_blueprint(conduit_bp)
    except: pass
    try:
        from copilot_core.api.v1.signal import signal_bp
        app.register_blueprint(signal_bp)
    except: pass
    try:
        from copilot_core.api.v1.session import session_bp
        app.register_blueprint(session_bp)
    except: pass
    try:
        from copilot_core.api.v1.xmpp import xmpp_bp
        app.register_blueprint(xmpp_bp)
    except: pass
    try:
        from copilot_core.api.v1.irc import irc_bp
        app.register_blueprint(irc_bp)
    except: pass
    try:
        from copilot_core.api.v1.mattermost import mattermost_bp
        app.register_blueprint(mattermost_bp)
    except: pass
    try:
        from copilot_core.api.v1.rocketchat import rocketchat_bp
        app.register_blueprint(rocketchat_bp)
    except: pass
    try:
        from copilot_core.api.v1.zulip import zulip_bp
        app.register_blueprint(zulip_bp)
    except: pass
    try:
        from copilot_core.api.v1.tox import tox_bp
        app.register_blueprint(tox_bp)
    except: pass
    try:
        from copilot_core.api.v1.simplex import simplex_bp
        app.register_blueprint(simplex_bp)
    except: pass
    try:
        from copilot_core.api.v1.deltachat import deltachat_bp
        app.register_blueprint(deltachat_bp)
    except: pass
    try:
        from copilot_core.api.v1.keybase import keybase_bp
        app.register_blueprint(keybase_bp)
    except: pass
    try:
        from copilot_core.api.v1.threema import threema_bp
        app.register_blueprint(threema_bp)
    except: pass
    try:
        from copilot_core.api.v1.wire import wire_bp
        app.register_blueprint(wire_bp)
    except: pass
    try:
        from copilot_core.api.v1.statusim import status_bp
        app.register_blueprint(status_bp)
    except: pass
    try:
        from copilot_core.api.v1.briar import briar_bp
        app.register_blueprint(briar_bp)
    except: pass
    try:
        from copilot_core.api.v1.jmap import jmap_bp
        app.register_blueprint(jmap_bp)
    except: pass
    try:
        from copilot_core.api.v1.fastmail import fastmail_bp
        app.register_blueprint(fastmail_bp)
    except: pass
    try:
        from copilot_core.api.v1.protonmail import protonmail_bp
        app.register_blueprint(protonmail_bp)
    except: pass
    try:
        from copilot_core.api.v1.tutanota import tutanota_bp
        app.register_blueprint(tutanota_bp)
    except: pass
    try:
        from copilot_core.api.v1.mailu import mailu_bp
        app.register_blueprint(mailu_bp)
    except: pass
    try:
        from copilot_core.api.v1.roundcube import roundcube_bp
        app.register_blueprint(roundcube_bp)
    except: pass
    try:
        from copilot_core.api.v1.sogo import sogo_bp
        app.register_blueprint(sogo_bp)
    except: pass
    try:
        from copilot_core.api.v1.zpush import zpush_bp
        app.register_blueprint(zpush_bp)
    except: pass
    try:
        from copilot_core.api.v1.davmail import davmail_bp
        app.register_blueprint(davmail_bp)
    except: pass
    try:
        from copilot_core.api.v1.kopano import kopano_bp
        app.register_blueprint(kopano_bp)
    except: pass
    try:
        from copilot_core.api.v1.radicale import radicale_bp
        app.register_blueprint(radicale_bp)
    except: pass
    try:
        from copilot_core.api.v1.baikal import baikal_bp
        app.register_blueprint(baikal_bp)
    except: pass
    try:
        from copilot_core.api.v1.nextcloud import nextcloud_bp
        app.register_blueprint(nextcloud_bp)
    except: pass
    try:
        from copilot_core.api.v1.owncloud import owncloud_bp
        app.register_blueprint(owncloud_bp)
    except: pass
    try:
        from copilot_core.api.v1.seafile import seafile_bp
        app.register_blueprint(seafile_bp)
    except: pass
    try:
        from copilot_core.api.v1.pydio import pydio_bp
        app.register_blueprint(pydio_bp)
    except: pass
    try:
        from copilot_core.api.v1.filestash import filestash_bp
        app.register_blueprint(filestash_bp)
    except: pass
    try:
        from copilot_core.api.v1.s3 import s3_bp
        app.register_blueprint(s3_bp)
    except: pass
    try:
        from copilot_core.api.v1.minio import minio_bp
        app.register_blueprint(minio_bp)
    except: pass
    try:
        from copilot_core.api.v1.rclone import rclone_bp
        app.register_blueprint(rclone_bp)
    except: pass
    try:
        from copilot_core.api.v1.borg import borg_bp
        app.register_blueprint(borg_bp)
    except: pass
    try:
        from copilot_core.api.v1.restic import restic_bp
        app.register_blueprint(restic_bp)
    except: pass
    try:
        from copilot_core.api.v1.duplicati import duplicati_bp
        app.register_blueprint(duplicati_bp)
    except: pass
    try:
        from copilot_core.api.v1.duplicacy import duplicacy_bp
        app.register_blueprint(duplicacy_bp)
    except: pass
    try:
        from copilot_core.api.v1.kopia import kopia_bp
        app.register_blueprint(kopia_bp)
    except: pass
    try:
        from copilot_core.api.v1.velero import velero_bp
        app.register_blueprint(velero_bp)
    except: pass
    try:
        from copilot_core.api.v1.kasten import kasten_bp
        app.register_blueprint(kasten_bp)
    except: pass
    try:
        from copilot_core.api.v1.trilio import trilio_bp
        app.register_blueprint(trilio_bp)
    except: pass
    try:
        from copilot_core.api.v1.rancher import rancher_bp
        app.register_blueprint(rancher_bp)
    except: pass
    try:
        from copilot_core.api.v1.portainer import portainer_bp
        app.register_blueprint(portainer_bp)
    except: pass
    try:
        from copilot_core.api.v1.traefik import traefik_bp
        app.register_blueprint(traefik_bp)
    except: pass
    try:
        from copilot_core.api.v1.npm import npm_bp
        app.register_blueprint(npm_bp)
    except: pass
    try:
        from copilot_core.api.v1.caddy import caddy_bp
        app.register_blueprint(caddy_bp)
    except: pass
    try:
        from copilot_core.api.v1.haproxy import haproxy_bp
        app.register_blueprint(haproxy_bp)
    except: pass
    try:
        from copilot_core.api.v1.envoy import envoy_bp
        app.register_blueprint(envoy_bp)
    except: pass
    try:
        from copilot_core.api.v1.k8s import k8s_bp
        app.register_blueprint(k8s_bp)
    except: pass
    try:
        from copilot_core.api.v1.helm import helm_bp
        app.register_blueprint(helm_bp)
    except: pass
    try:
        from copilot_core.api.v1.argocd import argocd_bp
        app.register_blueprint(argocd_bp)
    except: pass
    try:
        from copilot_core.api.v1.flux import flux_bp
        app.register_blueprint(flux_bp)
    except: pass
    try:
        from copilot_core.api.v1.k3s import k3s_bp
        app.register_blueprint(k3s_bp)
    except: pass
    try:
        from copilot_core.api.v1.minikube import minikube_bp
        app.register_blueprint(minikube_bp)
    except: pass
    try:
        from copilot_core.api.v1.kind import kind_bp
        app.register_blueprint(kind_bp)
    except: pass
    try:
        from copilot_core.api.v1.kubeadm import kubeadm_bp
        app.register_blueprint(kubeadm_bp)
    except: pass
    try:
        from copilot_core.api.v1.kubefed import kubefed_bp
        app.register_blueprint(kubefed_bp)
    except: pass
    try:
        from copilot_core.api.v1.opa import opa_bp
        app.register_blueprint(opa_bp)
    except: pass
    try:
        from copilot_core.api.v1.istio import istio_bp
        app.register_blueprint(istio_bp)
    except: pass
    try:
        from copilot_core.api.v1.linkerd import linkerd_bp
        app.register_blueprint(linkerd_bp)
    except: pass
    try:
        from copilot_core.api.v1.consul import consul_bp
        app.register_blueprint(consul_bp)
    except: pass
    try:
        from copilot_core.api.v1.vault import vault_bp
        app.register_blueprint(vault_bp)
    except: pass
    try:
        from copilot_core.api.v1.nomad import nomad_bp
        app.register_blueprint(nomad_bp)
    except: pass
    try:
        from copilot_core.api.v1.terraform import terraform_bp
        app.register_blueprint(terraform_bp)
    except: pass
    try:
        from copilot_core.api.v1.pulumi import pulumi_bp
        app.register_blueprint(pulumi_bp)
    except: pass
    try:
        from copilot_core.api.v1.ansible import ansible_bp
        app.register_blueprint(ansible_bp)
    except: pass
    try:
        from copilot_core.api.v1.chef import chef_bp
        app.register_blueprint(chef_bp)
    except: pass
    try:
        from copilot_core.api.v1.puppet import puppet_bp
        app.register_blueprint(puppet_bp)
    except: pass
    try:
        from copilot_core.api.v1.salt import salt_bp
        app.register_blueprint(salt_bp)
    except: pass
    try:
        from copilot_core.api.v1.cloudinit import cloudinit_bp
        app.register_blueprint(cloudinit_bp)
    except: pass
    try:
        from copilot_core.api.v1.packer import packer_bp
        app.register_blueprint(packer_bp)
    except: pass
    try:
        from copilot_core.api.v1.vagrant import vagrant_bp
        app.register_blueprint(vagrant_bp)
    except: pass
    try:
        from copilot_core.api.v1.proxmox import proxmox_bp
        app.register_blueprint(proxmox_bp)
    except: pass
    try:
        from copilot_core.api.v1.ovirt import ovirt_bp
        app.register_blueprint(ovirt_bp)
    except: pass
    try:
        from copilot_core.api.v1.openstack import openstack_bp
        app.register_blueprint(openstack_bp)
    except: pass
    try:
        from copilot_core.api.v1.vmware import vmware_bp
        app.register_blueprint(vmware_bp)
    except: pass
    try:
        from copilot_core.api.v1.hyperv import hyperv_bp
        app.register_blueprint(hyperv_bp)
    except: pass
    try:
        from copilot_core.api.v1.xen import xen_bp
        app.register_blueprint(xen_bp)
    except: pass
    try:
        from copilot_core.api.v1.libvirt import libvirt_bp
        app.register_blueprint(libvirt_bp)
    except: pass
    try:
        from copilot_core.api.v1.qemu import qemu_bp
        app.register_blueprint(qemu_bp)
    except: pass
    try:
        from copilot_core.api.v1.kvm import kvm_bp
        app.register_blueprint(kvm_bp)
    except: pass
    try:
        from copilot_core.api.v1.vbox import vbox_bp
        app.register_blueprint(vbox_bp)
    except: pass
    try:
        from copilot_core.api.v1.esxi import esxi_bp
        app.register_blueprint(esxi_bp)
    except: pass
    try:
        from copilot_core.api.v1.ceph import ceph_bp
        app.register_blueprint(ceph_bp)
    except: pass
    try:
        from copilot_core.api.v1.glusterfs import glusterfs_bp
        app.register_blueprint(glusterfs_bp)
    except: pass
    try:
        from copilot_core.api.v1.zfs import zfs_bp
        app.register_blueprint(zfs_bp)
    except: pass
    try:
        from copilot_core.api.v1.btrfs import btrfs_bp
        app.register_blueprint(btrfs_bp)
    except: pass
    try:
        from copilot_core.api.v1.xfs import xfs_bp
        app.register_blueprint(xfs_bp)
    except: pass
    try:
        from copilot_core.api.v1.longhorn import longhorn_bp
        app.register_blueprint(longhorn_bp)
    except: pass
    try:
        from copilot_core.api.v1.rook import rook_bp
        app.register_blueprint(rook_bp)
    except: pass
    try:
        from copilot_core.api.v1.openebs import openebs_bp
        app.register_blueprint(openebs_bp)
    except: pass
    try:
        from copilot_core.api.v1.minio_op import minio_op_bp
        app.register_blueprint(minio_op_bp)
    except: pass
    try:
        from copilot_core.api.v1.prom_op import prom_op_bp
        app.register_blueprint(prom_op_bp)
    except: pass
    try:
        from copilot_core.api.v1.certmanager import certmanager_bp
        app.register_blueprint(certmanager_bp)
    except: pass
    try:
        from copilot_core.api.v1.extdns import extdns_bp
        app.register_blueprint(extdns_bp)
    except: pass
    try:
        from copilot_core.api.v1.nginx_ing import nginx_ing_bp
        app.register_blueprint(nginx_ing_bp)
    except: pass
    try:
        from copilot_core.api.v1.metallb import metallb_bp
        app.register_blueprint(metallb_bp)
    except: pass
    try:
        from copilot_core.api.v1.coredns import coredns_bp
        app.register_blueprint(coredns_bp)
    except: pass
    try:
        from copilot_core.api.v1.foreman import foreman_bp
        app.register_blueprint(foreman_bp)
    except: pass
    try:
        from copilot_core.api.v1.katello import katello_bp
        app.register_blueprint(katello_bp)
    except: pass
    try:
        from copilot_core.api.v1.pulp import pulp_bp
        app.register_blueprint(pulp_bp)
    except: pass
    try:
        from copilot_core.api.v1.cobbler import cobbler_bp
        app.register_blueprint(cobbler_bp)
    except: pass
    try:
        from copilot_core.api.v1.pxe import pxe_bp
        app.register_blueprint(pxe_bp)
    except: pass
    try:
        from copilot_core.api.v1.ipxe import ipxe_bp
        app.register_blueprint(ipxe_bp)
    except: pass
    try:
        from copilot_core.api.v1.grub import grub_bp
        app.register_blueprint(grub_bp)
    except: pass
    try:
        from copilot_core.api.v1.syslinux import syslinux_bp
        app.register_blueprint(syslinux_bp)
    except: pass
    try:
        from copilot_core.api.v1.pxelinux import pxelinux_bp
        app.register_blueprint(pxelinux_bp)
    except: pass
    try:
        from copilot_core.api.v1.refind import refind_bp
        app.register_blueprint(refind_bp)
    except: pass
    try:
        from copilot_core.api.v1.cockpit import cockpit_bp
        app.register_blueprint(cockpit_bp)
    except: pass
    try:
        from copilot_core.api.v1.webmin import webmin_bp
        app.register_blueprint(webmin_bp)
    except: pass
    try:
        from copilot_core.api.v1.cpanel import cpanel_bp
        app.register_blueprint(cpanel_bp)
    except: pass
    try:
        from copilot_core.api.v1.plesk import plesk_bp
        app.register_blueprint(plesk_bp)
    except: pass
    try:
        from copilot_core.api.v1.directadmin import directadmin_bp
        app.register_blueprint(directadmin_bp)
    except: pass
    try:
        from copilot_core.api.v1.ispconfig import ispconfig_bp
        app.register_blueprint(ispconfig_bp)
    except: pass
    try:
        from copilot_core.api.v1.froxlor import froxlor_bp
        app.register_blueprint(froxlor_bp)
    except: pass
    try:
        from copilot_core.api.v1.virtualizor import virtualizor_bp
        app.register_blueprint(virtualizor_bp)
    except: pass
    try:
        from copilot_core.api.v1.solusvm import solusvm_bp
        app.register_blueprint(solusvm_bp)
    except: pass
    try:
        from copilot_core.api.v1.whmcs import whmcs_bp
        app.register_blueprint(whmcs_bp)
    except: pass
    try:
        from copilot_core.api.v1.postfix import postfix_bp
        app.register_blueprint(postfix_bp)
    except: pass
    try:
        from copilot_core.api.v1.dovecot import dovecot_bp
        app.register_blueprint(dovecot_bp)
    except: pass
    try:
        from copilot_core.api.v1.exim import exim_bp
        app.register_blueprint(exim_bp)
    except: pass
    try:
        from copilot_core.api.v1.sendmail import sendmail_bp
        app.register_blueprint(sendmail_bp)
    except: pass
    try:
        from copilot_core.api.v1.smtpd import smtpd_bp
        app.register_blueprint(smtpd_bp)
    except: pass
    try:
        from copilot_core.api.v1.opendkim import opendkim_bp
        app.register_blueprint(opendkim_bp)
    except: pass
    try:
        from copilot_core.api.v1.spf import spf_bp
        app.register_blueprint(spf_bp)
    except: pass
    try:
        from copilot_core.api.v1.dmarc import dmarc_bp
        app.register_blueprint(dmarc_bp)
    except: pass
    try:
        from copilot_core.api.v1.dkim import dkim_bp
        app.register_blueprint(dkim_bp)
    except: pass
    try:
        from copilot_core.api.v1.arc import arc_bp
        app.register_blueprint(arc_bp)
    except: pass
    try:
        from copilot_core.api.v1.clamav import clamav_bp
        app.register_blueprint(clamav_bp)
    except: pass
    try:
        from copilot_core.api.v1.rspamd import rspamd_bp
        app.register_blueprint(rspamd_bp)
    except: pass
    try:
        from copilot_core.api.v1.spamassassin import spamassassin_bp
        app.register_blueprint(spamassassin_bp)
    except: pass
    try:
        from copilot_core.api.v1.amavis import amavis_bp
        app.register_blueprint(amavis_bp)
    except: pass
    try:
        from copilot_core.api.v1.mailscanner import mailscanner_bp
        app.register_blueprint(mailscanner_bp)
    except: pass
    try:
        from copilot_core.api.v1.postgrey import postgrey_bp
        app.register_blueprint(postgrey_bp)
    except: pass
    try:
        from copilot_core.api.v1.razor import razor_bp
        app.register_blueprint(razor_bp)
    except: pass
    try:
        from copilot_core.api.v1.pyzor import pyzor_bp
        app.register_blueprint(pyzor_bp)
    except: pass
    try:
        from copilot_core.api.v1.dcc import dcc_bp
        app.register_blueprint(dcc_bp)
    except: pass
    try:
        from copilot_core.api.v1.rmilter import rmilter_bp
        app.register_blueprint(rmilter_bp)
    except: pass
    try:
        from copilot_core.api.v1.openldap import openldap_bp
        app.register_blueprint(openldap_bp)
    except: pass
    try:
        from copilot_core.api.v1.ds389 import ds389_bp
        app.register_blueprint(ds389_bp)
    except: pass
    try:
        from copilot_core.api.v1.freeipa import freeipa_bp
        app.register_blueprint(freeipa_bp)
    except: pass
    try:
        from copilot_core.api.v1.sambaad import sambaad_bp
        app.register_blueprint(sambaad_bp)
    except: pass
    try:
        from copilot_core.api.v1.kerberos import kerberos_bp
        app.register_blueprint(kerberos_bp)
    except: pass
    try:
        from copilot_core.api.v1.sssd import sssd_bp
        app.register_blueprint(sssd_bp)
    except: pass
    try:
        from copilot_core.api.v1.winbind import winbind_bp
        app.register_blueprint(winbind_bp)
    except: pass
    try:
        from copilot_core.api.v1.nscd import nscd_bp
        app.register_blueprint(nscd_bp)
    except: pass
    try:
        from copilot_core.api.v1.nss import nss_bp
        app.register_blueprint(nss_bp)
    except: pass
    try:
        from copilot_core.api.v1.pam import pam_bp
        app.register_blueprint(pam_bp)
    except: pass
    try:
        from copilot_core.api.v1.freeradius import freeradius_bp
        app.register_blueprint(freeradius_bp)
    except: pass
    try:
        from copilot_core.api.v1.oidc import oidc_bp
        app.register_blueprint(oidc_bp)
    except: pass
    try:
        from copilot_core.api.v1.saml import saml_bp
        app.register_blueprint(saml_bp)
    except: pass
    try:
        from copilot_core.api.v1.oauth2 import oauth2_bp
        app.register_blueprint(oauth2_bp)
    except: pass
    try:
        from copilot_core.api.v1.ldap import ldap_bp
        app.register_blueprint(ldap_bp)
    except: pass
    try:
        from copilot_core.api.v1.keycloak import keycloak_bp
        app.register_blueprint(keycloak_bp)
    except: pass
    try:
        from copilot_core.api.v1.dex import dex_bp
        app.register_blueprint(dex_bp)
    except: pass
    try:
        from copilot_core.api.v1.oauth2proxy import oauth2proxy_bp
        app.register_blueprint(oauth2proxy_bp)
    except: pass
    try:
        from copilot_core.api.v1.authelia import authelia_bp
        app.register_blueprint(authelia_bp)
    except: pass
    try:
        from copilot_core.api.v1.lldap import lldap_bp
        app.register_blueprint(lldap_bp)
    except: pass
    try:
        from copilot_core.api.v1.authentik import authentik_bp
        app.register_blueprint(authentik_bp)
    except: pass
    try:
        from copilot_core.api.v1.zitadel import zitadel_bp
        app.register_blueprint(zitadel_bp)
    except: pass
    try:
        from copilot_core.api.v1.casdoor import casdoor_bp
        app.register_blueprint(casdoor_bp)
    except: pass
    try:
        from copilot_core.api.v1.lemmy import lemmy_bp
        app.register_blueprint(lemmy_bp)
    except: pass
    try:
        from copilot_core.api.v1.pixelfed import pixelfed_bp
        app.register_blueprint(pixelfed_bp)
    except: pass
