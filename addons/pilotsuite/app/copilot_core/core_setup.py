"""
Core Setup - Service initialization and blueprint registration.

Extracted from main.py to follow modular architecture pattern.
"""

import logging
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
        from copilot_core.api.v1.shopping import shopping_bp
        app.register_blueprint(shopping_bp)
        _LOGGER.info("Registered Shopping/Reminders API (/api/v1/shopping/*, /api/v1/reminders/*)")
    except Exception:
        _LOGGER.exception("Failed to register Shopping/Reminders API")

    # Register Vector Store API (v3.5.0)
    try:
        from copilot_core.api.v1.vector import bp as vector_bp
        app.register_blueprint(vector_bp, url_prefix="/api/v1")
        _LOGGER.info("Registered Vector API (/api/v1/vector/*)")
    except Exception:
        _LOGGER.exception("Failed to register Vector API")

    # Register Error Status API (v7.8.10 — Error Dashboard Widget)
    try:
        from copilot_core.api.v1.error_status import api_bp
        app.register_blueprint(api_bp)
        _LOGGER.info("Registered Error Status API (/api/v1/errors/*)")
    except Exception:
        _LOGGER.exception("Failed to register Error Status API")
        _LOGGER.exception("Failed to register Vector API")

    # Register Sharing API (fix: was never wired)
    try:
        from copilot_core.sharing.api import sharing_bp
        app.register_blueprint(sharing_bp)
        _LOGGER.info("Registered Sharing API (/api/v1/sharing/*)")
    except Exception:
        _LOGGER.exception("Failed to register Sharing API")

    # Register Onyx bridge API (deterministic action bridge)
    try:
        from copilot_core.api.v1.onyx_bridge import onyx_bridge_bp
        app.register_blueprint(onyx_bridge_bp)
        _LOGGER.info("Registered Onyx bridge API (/api/v1/onyx/*)")
    except Exception:
        _LOGGER.exception("Failed to register Onyx bridge API")

    # Register PilotSuite MCP Server (expose skills to external AI clients)
    from copilot_core.mcp_server import mcp_bp
    app.register_blueprint(mcp_bp)
    
    # Register PilotSuite Hub API (v7.6.0 — 17 engines, 120+ endpoints)
    try:
        from copilot_core.hub.api import hub_bp, init_hub_api
        if services:
            init_hub_api(
                dashboard=services.get("hub_dashboard"),
                plugin_manager=services.get("hub_plugin_manager"),
                multi_home=services.get("hub_multi_home"),
                maintenance_engine=services.get("hub_maintenance"),
                anomaly_engine=services.get("hub_anomaly"),
                zone_engine=services.get("hub_zones"),
                light_engine=services.get("hub_light"),
                mode_engine=services.get("hub_modes"),
                media_engine=services.get("hub_media"),
                energy_advisor=services.get("hub_energy"),
                template_engine=services.get("hub_templates"),
                scene_engine=services.get("hub_scenes"),
                presence_engine=services.get("hub_presence"),
                notification_engine=services.get("hub_notifications"),
                integration_hub=services.get("hub_integration"),
                brain_architecture=services.get("hub_brain_arch"),
                brain_activity=services.get("hub_brain_activity"),
            )
        app.register_blueprint(hub_bp)
        _LOGGER.info("Registered Hub API (/api/v1/hub/* — 120+ endpoints)")
    except Exception:
        _LOGGER.exception("Failed to register Hub API")

    # Store services in app config for conversation context injection
    if services:
        app.config["COPILOT_SERVICES"] = services

    # Set global service instances for API access
    if services:
        from copilot_core import set_system_health_service
        if services.get("system_health_service"):
            set_system_health_service(services["system_health_service"])
        
        # Set SQL connection pool
        from copilot_core.performance import sql_pool
        if sql_pool:
            sql_pool.max_connections = 5  # Configure pool size
        
        # Set UniFi service for API access
        from copilot_core.unifi import set_unifi_service as set_unifi
        if services.get("unifi_service"):
            set_unifi(services["unifi_service"])
        
        # Set Energy service for API access
        from copilot_core.energy.api import init_energy_api
        if services.get("energy_service"):
            init_energy_api(services["energy_service"])
