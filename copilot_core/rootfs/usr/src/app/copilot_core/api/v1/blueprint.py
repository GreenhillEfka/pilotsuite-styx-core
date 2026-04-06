from flask import Blueprint

# Sub-blueprints with RELATIVE prefixes (nested under api_v1 /api/v1)
from copilot_core.api.v1.candidates import bp as candidates_bp
from copilot_core.api.v1.dev import bp as dev_bp
# RETIRED 2026-03-25: events_ingest.py is now canonical
# from copilot_core.api.v1.events import bp as events_bp  # LEGACY — do not reuse
from copilot_core.api.v1.mood import bp as mood_bp
from copilot_core.api.v1.graph import bp as graph_bp
from copilot_core.api.v1.habitus import bp as habitus_bp
from copilot_core.api.v1.habitus_dashboard_cards import bp as dashboard_cards_bp
from copilot_core.api.v1.graph_ops import bp as graph_ops_bp
from copilot_core.api.v1.vector import bp as vector_bp
from copilot_core.api.v1.neurons import bp as neurons_bp
from copilot_core.api.v1.neurons_visualization import bp as neurons_viz_bp
from copilot_core.api.v1.weather import bp as weather_bp
from copilot_core.api.v1.voice_context_bp import bp as voice_context_bp
from copilot_core.api.v1.swagger_ui import bp as swagger_ui_bp, openapi_bp
from copilot_core.api.v1.user_preferences import bp as user_preferences_bp
from copilot_core.api.v1.dashboard import bp as dashboard_bp
from copilot_core.knowledge_graph.api import bp as knowledge_graph_bp

# New feature APIs
from copilot_core.api.v1.search import bp as search_bp
from copilot_core.api.v1.notifications import bp as notifications_bp
from copilot_core.api.v1.user_hints import bp as user_hints_bp
from copilot_core.api.v1.conversation import conversation_bp
from copilot_core.api.v1.preferences import bp as preferences_bp
from copilot_core.api.v1.calendar import bp as calendar_bp

# Phase 5: Cross-Home Sync and Collective Intelligence
from copilot_core.sharing.api import sharing_bp
from copilot_core.collective_intelligence.api import federated_bp

# Rate Limiting API
from copilot_core.api.v1.rate_limit import rate_limit_bp

# HomeAssistant Discovery API
from copilot_core.homeassistant.api import ha_discovery_bp

# Metrics API (Flask)
from copilot_core.api.v1.metrics import metrics_bp

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# Register sub-blueprints with relative url_prefix (e.g. /neurons, /kg)
# These are correctly nested under /api/v1
api_v1.register_blueprint(dev_bp)
# events_bp retired 2026-03-25 — events_ingest.py is now canonical
api_v1.register_blueprint(candidates_bp)
api_v1.register_blueprint(mood_bp)
api_v1.register_blueprint(graph_bp)
api_v1.register_blueprint(habitus_bp)
api_v1.register_blueprint(dashboard_cards_bp)
api_v1.register_blueprint(graph_ops_bp)
api_v1.register_blueprint(vector_bp)
api_v1.register_blueprint(neurons_bp)
api_v1.register_blueprint(neurons_viz_bp)
api_v1.register_blueprint(weather_bp)
api_v1.register_blueprint(voice_context_bp)
api_v1.register_blueprint(swagger_ui_bp)
api_v1.register_blueprint(openapi_bp)
api_v1.register_blueprint(user_preferences_bp)
api_v1.register_blueprint(dashboard_bp)
api_v1.register_blueprint(knowledge_graph_bp)

# Register new feature APIs
api_v1.register_blueprint(search_bp)
api_v1.register_blueprint(notifications_bp)
api_v1.register_blueprint(user_hints_bp)

# Extended OpenAI Conversation support
api_v1.register_blueprint(conversation_bp)

# Register Multi-User Preference Learning API (P1-003)
api_v1.register_blueprint(preferences_bp)

# Register Calendar API
api_v1.register_blueprint(calendar_bp)

# Register Phase 5 APIs
api_v1.register_blueprint(sharing_bp)
api_v1.register_blueprint(federated_bp)

# Register Rate Limiting API
api_v1.register_blueprint(rate_limit_bp)

# Register HomeAssistant Discovery API
api_v1.register_blueprint(ha_discovery_bp)

# Register Metrics API (Flask)
api_v1.register_blueprint(metrics_bp)

# Module APIs (Slices 67-82)
from copilot_core.api.v1.modules import modules_bp

# Register Module APIs
api_v1.register_blueprint(modules_bp)

# Note: Additional standalone blueprints (habitus_zones, mcp, rag, styx_chat,
# sonos, zone_automation, etc.) are registered directly on the Flask app via
# core_setup.register_blueprints(). They must NOT be nested here to avoid
# double /api/v1/api/v1/ prefixes.

# Additional blueprints with /api/v1 prefix (added 2026-04-02)
from copilot_core.api.v1.ml_forecast import ml_forecast_bp
from copilot_core.api.v1.cache_control import cache_control_bp
from copilot_core.api.v1.ha_events import ha_events_bp
from copilot_core.api.v1.learning_viz import learning_viz_bp
from copilot_core.api.v1.media_ui import media_ui_bp
from copilot_core.api.v1.neurons_ui import neurons_ui_bp
from copilot_core.api.v1.rag_ui import rag_ui_bp
from copilot_core.api.v1.zone_automation_api import zone_automation_api_bp
from copilot_core.api.v1.backend_ui import backend_ui_bp
from copilot_core.api.v1.sensors import sensors_bp
from copilot_core.api.v1.auth import auth_bp
from copilot_core.api.v1.chat import chat_bp
from copilot_core.api.v1.energy_forecast import energy_forecast_bp
from copilot_core.api.v1.predictive import predictive_bp
from copilot_core.api.v1.advanced_analytics import advanced_analytics_bp

# Register additional blueprints
api_v1.register_blueprint(ml_forecast_bp)
api_v1.register_blueprint(cache_control_bp)
api_v1.register_blueprint(ha_events_bp)
api_v1.register_blueprint(learning_viz_bp)
api_v1.register_blueprint(media_ui_bp)
api_v1.register_blueprint(neurons_ui_bp)
api_v1.register_blueprint(rag_ui_bp)
api_v1.register_blueprint(zone_automation_api_bp)
api_v1.register_blueprint(backend_ui_bp)
api_v1.register_blueprint(sensors_bp)
api_v1.register_blueprint(auth_bp)
api_v1.register_blueprint(chat_bp)
api_v1.register_blueprint(energy_forecast_bp)
api_v1.register_blueprint(predictive_bp)
api_v1.register_blueprint(advanced_analytics_bp)
