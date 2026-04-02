"""PilotSuite Blueprints Configuration — Zentralisierte Blueprint-Registrierung.

Alle API-Blueprints werden hier definiert für konsistente Registrierung.
Prefix-Konvention: ALLE Endpoints unter /api/v1/*
"""

from typing import List, Tuple, Optional

# Blueprint-Konfiguration
# Format: (module_path, blueprint_name, url_prefix)
# - module_path: Python-Modulpfad (z.B. "copilot_core.api.v1.metrics")
# - blueprint_name: Name der Blueprint-Variable im Modul (z.B. "metrics_bp")
# - url_prefix: URL-Prefix (None wenn im Blueprint definiert)

# ============================================================================
# CORE API BLUEPRINTS (unter /api/v1)
# ============================================================================

CORE_API_BLUEPRINTS: List[Tuple[str, str, Optional[str]]] = [
    # System & Health
    ("copilot_core.api.v1.health", "health_bp", None),
    ("copilot_core.api.v1.metrics", "metrics_bp", None),
    ("copilot_core.api.v1.version", "version_bp", None),
    
    # Auth & Users
    ("copilot_core.api.v1.auth", "auth_bp", None),
    ("copilot_core.api.v1.users", "users_bp", None),
    
    # Zones & Automation
    ("copilot_core.api.v1.zones", "zones_bp", None),
    ("copilot_core.api.v1.zone_automation", "zone_automation_bp", None),
    ("copilot_core.api.v1.zone_automation_api", "zone_automation_api_bp", None),
    ("copilot_core.api.v1.zone_editor", "zone_editor_bp", None),
    ("copilot_core.api.v1.zone_aggregates", "zone_aggregates_bp", None),
    ("copilot_core.api.v1.zone_health", "zone_health_bp", None),
    ("copilot_core.api.v1.zone_dashboard", "zone_dashboard_bp", None),
    
    # Modules
    ("copilot_core.api.v1.modules", "modules_bp", None),
    ("copilot_core.api.v1.module_control", "module_control_bp", None),
    ("copilot_core.api.v1.module_health", "module_health_bp", None),
    ("copilot_core.api.v1.module_router_api", "module_router_bp", None),
    ("copilot_core.api.v1.zigbee_module", "zigbee_module_bp", None),
    ("copilot_core.api.v1.zwave_module", "zwave_module_bp", None),
    ("copilot_core.api.v1.thread_module", "thread_module_bp", None),
    ("copilot_core.api.v1.ha_module", "ha_module_bp", None),
    ("copilot_core.api.v1.sonos", "sonos_bp", None),
    ("copilot_core.api.v1.unifi_stub", "unifi_stub_bp", None),
    ("copilot_core.api.v1.regional_stub", "regional_stub_bp", None),
    ("copilot_core.api.v1.comfort_stub", "comfort_stub_bp", None),
    
    # Brain & Knowledge
    ("copilot_core.api.v1.habitus", "bp", None),
    ("copilot_core.api.v1.habitus_dashboard_cards", "bp", None),
    ("copilot_core.api.v1.graph", "bp", None),
    ("copilot_core.api.v1.graph_ops", "bp", None),
    ("copilot_core.api.v1.vector", "bp", None),
    ("copilot_core.api.v1.neurons", "bp", None),
    ("copilot_core.api.v1.neurons_ui", "neurons_ui_bp", None),
    ("copilot_core.api.v1.neurons_visualization", "bp", None),
    ("copilot_core.api.v1.neuron_layers", "neuron_layers_bp", None),
    ("copilot_core.api.v1.brain_growth", "brain_growth_bp", None),
    ("copilot_core.knowledge_graph.api", "bp", None),
    
    # Automation & Learning
    ("copilot_core.api.v1.mood", "bp", None),
    ("copilot_core.api.v1.learning_viz", "learning_viz_bp", None),
    ("copilot_core.api.v1.predictive", "predictive_bp", None),
    ("copilot_core.api.v1.suggestions", "suggestions_bp", None),
    ("copilot_core.api.v1.proposals", "proposals_bp", None),
    ("copilot_core.api.v1.candidates", "bp", None),
    ("copilot_core.api.v1.action_closure", "action_closure_bp", None),
    ("copilot_core.api.v1.action_attribution", "bp", None),
    ("copilot_core.api.v1.automation_api", "automation_bp", None),
    ("copilot_core.api.v1.autonomy", "autonomy_bp", None),
    ("copilot_core.api.v1.scenes", "scenes_bp", None),
    ("copilot_core.api.v1.multizone", "multizone_bp", None),
    
    # Energy & Forecasting
    ("copilot_core.api.v1.energy_forecast", "energy_forecast_bp", None),
    ("copilot_core.api.v1.ml_forecast", "ml_forecast_bp", None),
    ("copilot_core.api.v1.anomaly", "anomaly_bp", None),
    ("copilot_core.api.v1.energy_analytics", "analytics_bp", None),
    
    # RAG & Search
    ("copilot_core.api.v1.search", "bp", None),
    ("copilot_core.api.v1.rag", "rag_bp", None),
    ("copilot_core.api.v1.rag_ui", "rag_ui_bp", None),
    
    # Notifications & Communication
    ("copilot_core.api.v1.notifications", "bp", None),
    ("copilot_core.api.v1.chat", "chat_bp", None),
    ("copilot_core.api.v1.conversation", "conversation_bp", None),
    ("copilot_core.api.v1.voice_context_bp", "bp", None),
    ("copilot_core.api.v1.styx_voice", "styx_voice_bp", None),
    ("copilot_core.api.v1.user_hints", "user_hints_bp", None),
    ("copilot_core.api.v1.reminders", "reminders_bp", None),
    
    # Calendar & Events
    ("copilot_core.api.v1.calendar", "calendar_bp", None),
    ("copilot_core.api.v1.ha_events", "ha_events_bp", None),
    ("copilot_core.api.v1.events_ingest", "bp", None),
    
    # Cache & Performance
    ("copilot_core.api.v1.cache_control", "cache_control_bp", None),
    ("copilot_core.api.v1.performance", "performance_bp", None),
    ("copilot_core.api.v1.rate_limit", "rate_limit_bp", None),
    
    # Media & Entertainment
    ("copilot_core.api.v1.media_ui", "media_ui_bp", None),
    ("copilot_core.api.v1.media_zones", "media_zones_bp", None),
    ("copilot_core.api.v1.musikwolke", "musikwolke_bp", None),
    
    # Dashboard & UI
    ("copilot_core.api.v1.backend_ui", "backend_ui_bp", None),
    ("copilot_core.api.v1.dashboard", "bp", None),
    ("copilot_core.api.v1.styx_dashboard", "styx_dashboard_bp", None),
    ("dashboard.api.v1.widget_positions", "widget_positions_bp", None),
    
    # Config & Preferences
    ("copilot_core.api.v1.config", "config_bp", None),
    ("copilot_core.api.v1.user_preferences", "bp", None),
    ("copilot_core.api.v1.user_management", "user_management_bp", None),
    
    # Home & Multi-Home
    ("copilot_core.api.v1.homekit", "homekit_bp", None),
    ("copilot_core.sharing.api", "sharing_bp", None),
    ("copilot_core.api.v1.multihome", "bp", None),
    
    # Collective Intelligence
    ("copilot_core.collective_intelligence.api", "federated_bp", None),
    
    # Shopping & Haushalt
    ("copilot_core.api.v1.shopping", "shopping_bp", None),
    ("copilot_core.api.v1.haushalt", "haushalt_bp", None),
    
    # Errors & Debugging
    ("copilot_core.api.v1.error_digest", "error_digest_bp", None),
    ("copilot_core.api.v1.dev", "bp", None),
    ("copilot_core.api.v1.debug", "bp", None),
    ("copilot_core.api.v1.swagger_ui", "bp", None),
    
    # Entity Management
    ("copilot_core.api.v1.entity_adoption", "bp", None),
    ("copilot_core.api.v1.entity_assignment", "entity_assignment_bp", None),
    ("copilot_core.api.v1.entity_normalization", "entity_normalization_bp", None),
    
    # Advanced Features
    ("copilot_core.api.v1.alarm", "alarm_bp", None),
    ("copilot_core.api.v1.conflict_resolution", "bp", None),
    ("copilot_core.api.v1.explain", "explain_bp", None),
    ("copilot_core.api.v1.character", "bp", None),
    ("copilot_core.api.v1.openai_compat", "openai_compat_bp", None),
    ("copilot_core.api.v1.onyx_bridge", "onyx_bridge_bp", None),
    ("copilot_core.api.v1.mcp", "bp", None),
    ("copilot_core.api.v1.weather", "bp", None),
    
    # Security
    ("copilot_core.api.v1.security", "bp", None),
]

# ============================================================================
# EXTERNAL BLUEPRINTS (nicht unter /api/v1)
# ============================================================================

EXTERNAL_BLUEPRINTS: List[Tuple[str, str, str]] = [
    # OpenAI-compatible API (für Chat-Clients)
    ("copilot_core.api.v1.openai_compat", "openai_compat_bp", "/v1"),
    
    # HomeAssistant Discovery (für HA-Integration)
    ("copilot_core.homeassistant.api", "ha_discovery_bp", "/ha"),
    
    # MCP (Model Context Protocol)
    ("copilot_core.api.v1.mcp", "mcp_bp", "/mcp"),
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_all_blueprints() -> List[Tuple[str, str, Optional[str]]]:
    """Get all blueprints (core + external)."""
    return CORE_API_BLUEPRINTS + EXTERNAL_BLUEPRINTS


def get_core_api_blueprints() -> List[Tuple[str, str, Optional[str]]]:
    """Get only core API blueprints (under /api/v1)."""
    return CORE_API_BLUEPRINTS


def get_external_blueprints() -> List[Tuple[str, str, str]]:
    """Get external blueprints (not under /api/v1)."""
    return EXTERNAL_BLUEPRINTS


def validate_blueprint_config() -> Tuple[bool, List[str]]:
    """Validate blueprint configuration for consistency."""
    errors = []
    
    # Check for duplicate blueprint names
    seen_names = set()
    for module_path, bp_name, prefix in CORE_API_BLUEPRINTS:
        key = f"{module_path}.{bp_name}"
        if key in seen_names:
            errors.append(f"Duplicate blueprint: {key}")
        seen_names.add(key)
    
    # Check for consistent prefix pattern
    for module_path, bp_name, prefix in CORE_API_BLUEPRINTS:
        if prefix is not None and not prefix.startswith("/api/v1"):
            errors.append(f"Inconsistent prefix for {module_path}.{bp_name}: {prefix}")
    
    return len(errors) == 0, errors
