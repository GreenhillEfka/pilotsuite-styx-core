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
from copilot_core.mood.engine import UnifiedMoodEngine
from copilot_core.mood.models import MoodSystemConfig
from copilot_core.system_health.api import system_health_bp
from copilot_core.system_health.service import SystemHealthService
from copilot_core.unifi.api import unifi_bp, set_unifi_service
from copilot_core.unifi.service import UniFiService
from copilot_core.energy.api import energy_bp, init_energy_api
from copilot_core.energy.service import EnergyService
# Tag System v0.2 (Decision Matrix 2026-02-14)
from copilot_core.tags import TagRegistry, create_tag_service
from copilot_core.tags.api import init_tags_api as setup_tag_api
# Auto-setup API (v10.3.0 — zone suggestions + auto-tagging)
from copilot_core.api.v1.auto_setup import auto_setup_bp, init_auto_setup_api
from copilot_core.webhook_pusher import WebhookPusher
from copilot_core.household import HouseholdProfile
from copilot_core.neurons.manager import NeuronManager
from copilot_core.event_bus import EventBus, get_event_bus

# SearXNG web search integration (v7.11.1)
_SEARXNG_ENABLED = os.environ.get("SEARXNG_ENABLED", "false").lower() == "true"
_SEARXNG_BASE_URL = os.environ.get("SEARXNG_BASE_URL", "")

# PilotSuite Phase 5 APIs
from copilot_core.telegram import TelegramBot
from copilot_core.module_registry import ModuleRegistry
from copilot_core.automation_creator import AutomationCreator
from copilot_core.media_zone_manager import MediaZoneManager
from copilot_core.music_cloud import MusicCloudService
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

    # Initialize EventBus (central communication layer)
    event_bus = get_event_bus()

    services: dict = {
        "config": config,
        "event_bus": event_bus,
        "system_health_service": None,
        "unifi_service": None,
        "energy_service": None,
        "brain_graph_service": None,
        "graph_renderer": None,
        "candidate_store": None,
        "habitus_service": None,
        "mood_service": None,
        "mood_engine": None,
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
        "music_cloud_service": None,
        "proactive_engine": None,
        "web_search_service": None,
        "waste_service": None,
        "birthday_service": None,
        "vector_store": None,
        "embedding_engine": None,
        "rag_service": None,
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
        # Adaptive Light Module (v1.0.0)
        "light_module_service": None,
        # Zone Automation Controller (v10.0.0)
        "zone_automation_controller": None,
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

        # Subscribe to zone changes to update graph nodes
        def _on_zone_change(topic: str, data: dict) -> None:
            """Update brain graph when zones change."""
            try:
                zone_id = data.get("zone_id", "")
                if zone_id and brain_graph_service:
                    brain_graph_service.add_node(
                        entity_id=zone_id,
                        kind="zone",
                        state="active",
                        metadata={"name": data.get("name", zone_id)},
                    )
            except Exception:
                _LOGGER.debug("Brain graph zone node update failed")

        event_bus.subscribe("zone.updated", _on_zone_change)
        event_bus.subscribe("zone.synced", lambda t, d: event_bus.publish(
            "graph.updated", {"source": "zone_sync", "count": d.get("count", 0)},
            source="brain_graph"
        ))
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
            init_habitus_api(habitus_service, services["brain_graph_service"])
    except Exception:
        _LOGGER.exception("Failed to init HabitusService")

    # Initialize mood service, engine, and API
    try:
        mood_config_raw = config.get("mood", {}) if config else {}
        mood_system_config = MoodSystemConfig.from_dict(mood_config_raw) if mood_config_raw else MoodSystemConfig()

        mood_engine = UnifiedMoodEngine(mood_system_config)
        services["mood_engine"] = mood_engine
        _LOGGER.info("UnifiedMoodEngine initialized (%d zones)", len(mood_system_config.zones))

        mood_service = MoodService(config=mood_system_config)
        services["mood_service"] = mood_service
        init_mood_api(mood_service)

        # Wire EventBus: update mood when neurons report mood changes
        def _update_mood_from_neurons(topic: str, data: dict) -> None:
            """Update mood service from neuron pipeline results."""
            try:
                dominant_mood = data.get("dominant_mood", "")
                confidence = data.get("mood_confidence", 0.0)
                if dominant_mood and confidence > 0.3:
                    # Update mood for all active zones from habitus zone store
                    from copilot_core.api.v1.habitus_zones import get_all_zones
                    zones = get_all_zones()
                    for zone in zones:
                        zone_id = zone.get("zone_id", "")
                        if zone_id:
                            mood_service.update_zone_mood(zone_id, {
                                "dominant_mood": dominant_mood,
                                "confidence": confidence,
                            })
            except Exception:
                _LOGGER.debug("Mood update from neuron pipeline failed")

        event_bus.subscribe("neuron.evaluated", _update_mood_from_neurons)
    except Exception:
        _LOGGER.exception("Failed to init MoodService")

    # Initialize event processor: EventStore → BrainGraph pipeline
    try:
        if services["brain_graph_service"]:
            event_processor = EventProcessor(brain_graph_service=services["brain_graph_service"])
            services["event_processor"] = event_processor

            # Wire EventBus: event ingestion triggers graph updates + habitus mining
            def _post_ingest_with_bus(events):
                """Post-ingest callback: process events and publish to EventBus."""
                event_processor.process_events(events)
                # Feed entity data into searchable entity cache (v9.0.0)
                try:
                    from copilot_core.api.v1.entity_search import update_entity_cache
                    if events:
                        update_entity_cache(events)
                except Exception:
                    pass  # Non-critical: search cache is best-effort
                # Publish to EventBus for other modules
                event_bus.publish("event.ingested", {
                    "count": len(events) if events else 0,
                    "states": {
                        e.get("entity_id", ""): e.get("state_to", e.get("state", ""))
                        for e in (events or [])
                        if isinstance(e, dict) and e.get("entity_id")
                    },
                }, source="event_processor")

            set_post_ingest_callback(_post_ingest_with_bus)

            # Wire habitus mining on event ingestion
            habitus_svc = services.get("habitus_service")
            if habitus_svc:
                def _trigger_habitus_learning(topic: str, data: dict) -> None:
                    """Trigger habitus pattern mining after events are ingested."""
                    try:
                        cfg = habitus_svc.get_config() if hasattr(habitus_svc, "get_config") else {}
                        if not cfg or not isinstance(cfg, dict):
                            cfg = {}
                        if not cfg.get("mine_on_event_ingest", True):
                            return

                        # Respect module off-state if ModuleRegistry exists.
                        try:
                            from copilot_core.module_registry import ModuleRegistry
                            if ModuleRegistry.get_instance().is_off("habitus_miner"):
                                return
                        except Exception:
                            pass

                        count = int(data.get("count", 0) or 0)
                        min_events = int(cfg.get("min_events_per_batch", 5) or 5)
                        if count < min_events:
                            return

                        lookback = int(cfg.get("lookback_hours", 72) or 72)
                        result = habitus_svc.mine_and_create_candidates(
                            lookback_hours=lookback,
                            force=False,
                        )
                        new_candidates = int(result.get("candidates_created", 0) or 0) if isinstance(result, dict) else 0
                        if new_candidates > 0:
                            event_bus.publish(
                                "habitus.pattern",
                                {
                                    "new_patterns": new_candidates,
                                    "patterns_found": result.get("patterns_found", 0) if isinstance(result, dict) else 0,
                                },
                                source="habitus_service",
                            )
                    except Exception:
                        _LOGGER.debug("Habitus mining after event batch failed")

                event_bus.subscribe("event.ingested", _trigger_habitus_learning)
                _LOGGER.info("Habitus learning loop wired to EventBus")
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

        # Wire EventBus: publish mood changes and neuron evaluations
        def _on_mood_change_bus(mood: str, confidence: float) -> None:
            event_bus.publish("mood.changed", {
                "mood": mood, "confidence": confidence,
            }, source="neuron_manager")

        def _on_suggestion_bus(suggestion: dict) -> None:
            event_bus.publish("candidate.created", suggestion, source="neuron_manager")

        neuron_manager.on_mood_change(_on_mood_change_bus)
        neuron_manager.on_suggestion(_on_suggestion_bus)

        # Wire EventBus: update neuron states when events are ingested
        def _on_event_ingested(topic: str, data: dict) -> None:
            """Feed ingested HA events into neuron state updates."""
            try:
                states = data.get("states", {})
                if states:
                    neuron_manager.update_states(states)
            except Exception:
                _LOGGER.debug("Neuron state update from event bus failed")

        event_bus.subscribe("event.ingested", _on_event_ingested)

        # Periodic neuron evaluation via daemon thread
        neuron_eval_interval = _safe_int(
            neuron_config.get("evaluation_interval", 60), 60, 10, 3600
        )
        import threading
        def _periodic_neuron_eval():
            """Run neuron pipeline at configured interval."""
            import time
            while True:
                time.sleep(neuron_eval_interval)
                try:
                    result = neuron_manager.evaluate()
                    event_bus.publish("neuron.evaluated", {
                        "dominant_mood": result.dominant_mood,
                        "mood_confidence": result.mood_confidence,
                        "suggestion_count": len(result.suggestions),
                        "timestamp": result.timestamp,
                    }, source="neuron_manager")
                except Exception:
                    _LOGGER.debug("Periodic neuron evaluation failed")

        eval_thread = threading.Thread(
            target=_periodic_neuron_eval, daemon=True, name="neuron-eval"
        )
        eval_thread.start()
        _LOGGER.info("Neuron periodic evaluation started (%ds interval)", neuron_eval_interval)

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

    # Initialize RAG document service (v8.7.0)
    try:
        if services.get("vector_store") and services.get("embedding_engine"):
            from copilot_core.rag.service import RagService

            services["rag_service"] = RagService(
                vector_store=services["vector_store"],
                embedding_engine=services["embedding_engine"],
            )
            _LOGGER.info("RagService initialized")
    except Exception:
        _LOGGER.exception("Failed to init RagService")

    # Set conversation env vars from config (used by conversation.py + llm_provider.py)
    try:
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

    # Initialize Override Modes Service (Party/Vacation/Sleep/Eco/Guest)
    try:
        from copilot_core.override_modes import OverrideModesService
        override_modes_service = OverrideModesService(event_bus=event_bus)
        services["override_modes_service"] = override_modes_service
        _LOGGER.info("OverrideModesService initialized (6 built-in modes)")
    except Exception:
        _LOGGER.exception("Failed to init OverrideModesService")

    # Initialize Music Cloud Service (Sonos zone-following via motion sensors)
    try:
        music_cloud_service = MusicCloudService(
            media_zone_manager=services.get("media_zone_manager"),
            override_modes_service=services.get("override_modes_service"),
            event_bus=event_bus,
        )
        services["music_cloud_service"] = music_cloud_service
        _LOGGER.info("MusicCloudService initialized")
    except Exception:
        _LOGGER.exception("Failed to init MusicCloudService")

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

    # Initialize Adaptive Light Module Service (v1.0.0)
    try:
        from copilot_core.light_module.service import LightModuleService
        light_module_service = LightModuleService()
        services["light_module_service"] = light_module_service
        _LOGGER.info("LightModuleService initialized (adaptive lighting)")
    except Exception:
        _LOGGER.exception("Failed to init LightModuleService")

    # Initialize Zone Automation Controller (v10.0.0)
    # Coordinates presence, brightness, circadian light, mood, and media per zone.
    try:
        from copilot_core.zone_automation import ZoneAutomationController
        zone_automation_controller = ZoneAutomationController(
            event_bus=event_bus,
            light_module_service=services.get("light_module_service"),
            music_cloud_service=services.get("music_cloud_service"),
            override_modes_service=services.get("override_modes_service"),
        )
        services["zone_automation_controller"] = zone_automation_controller

        # Wire EventBus → ZoneAutomationController: forward sensor updates
        def _on_event_for_zone_automation(topic: str, data: dict) -> None:
            """Forward ingested HA events to zone automation for evaluation."""
            try:
                states = data.get("states", {})
                for entity_id, new_state in states.items():
                    zone_automation_controller.process_sensor_update(
                        entity_id, str(new_state), {}
                    )
            except Exception:
                _LOGGER.debug("Zone automation event forwarding failed")

        event_bus.subscribe("event.ingested", _on_event_for_zone_automation)
        _LOGGER.info("ZoneAutomationController wired to EventBus (event.ingested)")

        # Wire EventBus → OverrideModesService: vacation alarm on presence
        override_modes_svc = services.get("override_modes_service")
        if override_modes_svc:
            def _on_presence_for_vacation_alarm(topic: str, data: dict) -> None:
                """Check for vacation mode + presence → trigger alarm event."""
                try:
                    states = data.get("states", {})
                    for entity_id, new_state in states.items():
                        if "motion" in entity_id and str(new_state).lower() in ("on", "detected"):
                            consequences = override_modes_svc.get_effective_consequences("")
                            if consequences.get("presence_alarm"):
                                event_bus.publish("alarm.vacation_presence", {
                                    "entity_id": entity_id,
                                    "state": str(new_state),
                                    "message": f"Motion detected ({entity_id}) while vacation mode active",
                                }, source="override_modes")
                                _LOGGER.warning(
                                    "VACATION ALARM: Motion detected (%s) while vacation mode active",
                                    entity_id,
                                )
                except Exception:
                    _LOGGER.debug("Vacation alarm check failed")

            event_bus.subscribe("event.ingested", _on_presence_for_vacation_alarm)

        _LOGGER.info("ZoneAutomationController initialized (presence + light + brightness + media)")
    except Exception:
        _LOGGER.exception("Failed to init ZoneAutomationController")

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
    # Expose UnifiedMoodEngine on Flask config for mood API /dependencies endpoint
    if services and services.get("mood_engine"):
        app.config["MOOD_ENGINE"] = services["mood_engine"]
    app.register_blueprint(system_health_bp)
    app.register_blueprint(unifi_bp)
    app.register_blueprint(energy_bp)
    app.register_blueprint(performance_bp)  # Performance monitoring

    # Register Hub API (zone management, dashboard widgets, brain activity chat)
    try:
        from copilot_core.hub.api import hub_bp, init_hub_api
        init_hub_api(
            dashboard=services.get("hub_dashboard") if services else None,
            plugin_manager=services.get("hub_plugin_manager") if services else None,
            multi_home=services.get("hub_multi_home") if services else None,
            maintenance_engine=services.get("hub_maintenance") if services else None,
            anomaly_engine=services.get("hub_anomaly") if services else None,
            zone_engine=services.get("hub_zones") if services else None,
            light_engine=services.get("hub_light") if services else None,
            mode_engine=services.get("hub_modes") if services else None,
            media_engine=services.get("hub_media") if services else None,
            energy_advisor=services.get("hub_energy") if services else None,
            template_engine=services.get("hub_templates") if services else None,
            scene_engine=services.get("hub_scenes") if services else None,
            presence_engine=services.get("hub_presence") if services else None,
            notification_engine=services.get("hub_notifications") if services else None,
            integration_hub=services.get("hub_integration") if services else None,
            brain_architecture=services.get("hub_brain_arch") if services else None,
            brain_activity=services.get("hub_brain_activity") if services else None,
        )
        app.register_blueprint(hub_bp)
        _LOGGER.info("Registered Hub API (/api/v1/hub/*)")
    except Exception:
        _LOGGER.exception("Failed to register Hub API")

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

    # Register Auto-Setup API (v10.3.0 — zone suggestions + auto-tagging)
    try:
        tag_registry = services.get("tag_registry") if services else None
        init_auto_setup_api(tag_service=tag_registry)
        app.register_blueprint(auto_setup_bp)
        _LOGGER.info("Registered Auto-Setup API (/api/v1/auto-setup/*)")
    except Exception:
        _LOGGER.exception("Failed to register Auto-Setup API")

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

    # Register RAG API (v8.7.0)
    try:
        from copilot_core.api.v1.rag import rag_bp, init_rag_api

        if services and services.get("rag_service"):
            init_rag_api(services["rag_service"])
        app.register_blueprint(rag_bp)
        _LOGGER.info("Registered RAG API (/api/v1/rag/*)")
    except Exception:
        _LOGGER.exception("Failed to register RAG API")

    # Register User Hints API (/api/v1/hints/*)
    try:
        from copilot_core.api.v1.user_hints import bp as hints_bp, init_hints_service
        from copilot_core.api.v1.service import UserHintsService

        init_hints_service(
            UserHintsService(
                automation_creator=services.get("automation_creator") if services else None
            )
        )
        app.register_blueprint(hints_bp, url_prefix="/api/v1/hints")
        _LOGGER.info("Registered User Hints API (/api/v1/hints/*)")
    except Exception:
        _LOGGER.exception("Failed to register User Hints API")

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

    # Register Music Cloud API (Sonos zone-following via motion sensors)
    try:
        from copilot_core.api.v1.music_cloud import media_cloud_bp, init_music_cloud_api
        if services:
            init_music_cloud_api(
                services.get("music_cloud_service"),
                services.get("media_zone_manager"),
            )
        app.register_blueprint(media_cloud_bp)
        _LOGGER.info("Registered Music Cloud API (/api/v1/media/cloud/*)")
    except Exception:
        _LOGGER.exception("Failed to register Music Cloud API")

    # Register Override Modes API (Party/Vacation/Sleep/Eco/Guest)
    try:
        from copilot_core.api.v1.override_modes import override_modes_bp, init_override_modes_api
        if services and services.get("override_modes_service"):
            init_override_modes_api(services["override_modes_service"])
        app.register_blueprint(override_modes_bp)
        _LOGGER.info("Registered Override Modes API (/api/v1/modes/*)")
    except Exception:
        _LOGGER.exception("Failed to register Override Modes API")

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

    # ---- Simple blueprints (data-driven registration) ----
    # Each entry: (module_path, blueprint_attr, log_label)
    # These blueprints need no init_* call or special setup — just import + register.
    import importlib as _importlib

    _SIMPLE_BLUEPRINTS: list[tuple[str, str, str]] = [
        ("copilot_core.api.v1.haushalt", "haushalt_bp", "Haushalt API"),
        ("copilot_core.api.v1.entity_assignment", "entity_assignment_bp", "Entity Assignment API"),
        ("copilot_core.api.v1.presence", "presence_bp", "Presence API"),
        ("copilot_core.api.v1.scene_patterns", "scene_patterns_bp", "Scene Patterns API"),
        ("copilot_core.api.v1.routine_patterns", "routine_patterns_bp", "Routine Patterns API"),
        ("copilot_core.api.v1.push_notifications", "push_notifications_bp", "Push Notifications API"),
        ("copilot_core.api.v1.system_status", "system_status_bp", "System Status API"),
        ("copilot_core.api.v1.self_repair", "self_repair_bp", "Self-Repair API"),
        ("copilot_core.api.v1.automation_webhook", "automation_webhook_bp", "Automation Webhook API"),
        ("copilot_core.api.v1.service_calls", "services_bp", "Service Calls API"),
        ("copilot_core.api.v1.sensors", "sensors_bp", "Sensors API"),
        ("copilot_core.api.v1.lights", "lights_bp", "Lights API"),
        ("copilot_core.api.v1.climate", "climate_bp", "Climate API"),
        ("copilot_core.api.v1.switches", "switches_bp", "Switches API"),
        ("copilot_core.api.v1.media_players", "media_bp", "Media Players API"),
        ("copilot_core.api.v1.groups", "groups_bp", "Groups API"),
        ("copilot_core.api.v1.input_select", "input_select_bp", "Input Select API"),
        ("copilot_core.api.v1.scenes_v2", "scenes_v2_bp", "Scenes v2 API"),
        ("copilot_core.api.v1.covers", "covers_bp", "Covers API"),
        ("copilot_core.api.v1.fans", "fans_bp", "Fans API"),
        ("copilot_core.api.v1.webhooks", "webhooks_bp", "Webhooks API"),
        ("copilot_core.api.v1.summary", "summary_bp", "Summary API"),
        ("copilot_core.api.v1.history", "history_bp", "History API"),
        ("copilot_core.api.v1.locks", "locks_bp", "Locks API"),
        ("copilot_core.api.v1.alerts", "alerts_bp", "Alerts API"),
        ("copilot_core.api.v1.weather", "weather_bp", "Weather API"),
        ("copilot_core.api.v1.homekit", "homekit_bp", "HomeKit API"),
        ("copilot_core.api.v1.calendar", "calendar_bp", "Calendar API"),
        ("copilot_core.api.v1.shopping", "shopping_bp", "Shopping + Reminders API"),
        ("copilot_core.api.v1.input_number", "input_number_bp", "Input Number API"),
        ("copilot_core.api.v1.zones", "zones_bp", "Zones API"),
        ("copilot_core.api.v1.event_bus_api", "event_bus_api_bp", "EventBus API"),
        ("copilot_core.api.v1.entity_search", "entity_search_bp", "Entity Search API"),
        ("copilot_core.api.v1.config_management", "config_bp", "Config Management API"),
        ("copilot_core.api.v1.templates", "templates_bp", "Templates API"),
        ("copilot_core.api.v1.logbook", "logbook_bp", "Logbook API"),
        ("copilot_core.api.v1.repairs", "repairs_bp", "Repairs API"),
    ]

    _simple_ok = 0
    for _mod_path, _bp_attr, _label in _SIMPLE_BLUEPRINTS:
        try:
            _mod = _importlib.import_module(_mod_path)
            _bp = getattr(_mod, _bp_attr)
            app.register_blueprint(_bp)
            _simple_ok += 1
        except Exception:
            _LOGGER.exception("Failed to register %s", _label)

    _LOGGER.info("Simple blueprints: %d/%d registered", _simple_ok, len(_SIMPLE_BLUEPRINTS))

    # ---- Complex blueprints (require init_* calls or special setup) ----

    # Register Adaptive Light Module API (v1.0.0)
    try:
        from copilot_core.light_module.api import light_module_bp, init_light_module_api
        if services and services.get("light_module_service"):
            init_light_module_api(services["light_module_service"])
        app.register_blueprint(light_module_bp)
        _LOGGER.info("Registered Light Module API (/api/v1/light-module/*)")
    except Exception:
        _LOGGER.exception("Failed to register Light Module API")

    # Register Zone Automation API (v10.0.0)
    try:
        from copilot_core.zone_automation.api import zone_automation_bp, init_zone_automation_api
        if services and services.get("zone_automation_controller"):
            init_zone_automation_api(services["zone_automation_controller"])
        app.register_blueprint(zone_automation_bp)
        _LOGGER.info("Registered Zone Automation API (/api/v1/zone-automation/*)")
    except Exception:
        _LOGGER.exception("Failed to register Zone Automation API")

    # Register Scene Management API (v3.4.0) — with persistent storage
    try:
        from copilot_core.api.v1.scenes import scenes_bp, init_scene_store
        init_scene_store()
        app.register_blueprint(scenes_bp)
        _LOGGER.info("Registered Scenes API (/api/v1/scenes/*) — store loaded")
    except Exception:
        _LOGGER.exception("Failed to register Scenes API")

    # NOTE: Entity API is provided by Entity Search API v2 (/api/v1/entities/*).
    # The legacy entity-management blueprint depended on HA internals and caused
    # route collisions with the cache-backed search API. Keep it unregistered.

    # Register Habitus Zones API (v9.0.0 — bidirectional HA<->Core zone sync)
    try:
        from copilot_core.api.v1.habitus_zones import habitus_zones_bp, init_habitus_zones_api
        event_bus_ref = services.get("event_bus") if services else None
        init_habitus_zones_api(event_bus=event_bus_ref)
        app.register_blueprint(habitus_zones_bp)
        _LOGGER.info("Registered Habitus Zones API (/api/v1/habitus/zones/*)")
    except Exception:
        _LOGGER.exception("Failed to register Habitus Zones API")

    # Register HA Bridge API (v9.1.0 — discover HA data from within add-on)
    try:
        from copilot_core.api.v1.ha_bridge import ha_bridge_bp, auto_discover_on_startup
        app.register_blueprint(ha_bridge_bp)
        _LOGGER.info("Registered HA Bridge API (/api/v1/ha/discover, /status)")
        # Auto-discover HA entities on startup (background thread)
        auto_discover_on_startup()
    except Exception:
        _LOGGER.exception("Failed to register HA Bridge API")

    # Register legacy System Health API only if not already present.
    # The primary SystemHealth blueprint is registered above and already
    # exposes /api/v1/system_health*. This guard prevents duplicate
    # blueprint-name collisions ("system_health").
    try:
        from copilot_core.api.v1.system_health import (
            system_health_bp as system_health_v1_bp,
        )
        existing_bp = app.blueprints.get(system_health_v1_bp.name)
        if existing_bp is None:
            app.register_blueprint(system_health_v1_bp)
            _LOGGER.info("Registered System Health API (/api/v1/system_health/*)")
        else:
            _LOGGER.debug(
                "Skipping legacy System Health API registration (blueprint '%s' already present)",
                system_health_v1_bp.name,
            )
    except Exception:
        _LOGGER.exception("Failed to register System Health API")
