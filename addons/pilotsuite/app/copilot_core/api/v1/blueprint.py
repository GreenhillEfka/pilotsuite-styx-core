from flask import Blueprint

# Sub-blueprints with RELATIVE prefixes (nested under api_v1 /api/v1)
from copilot_core.api.v1.candidates import bp as candidates_bp
from copilot_core.api.v1.dev import bp as dev_bp
from copilot_core.api.v1.events import bp as events_bp
from copilot_core.api.v1.mood import bp as mood_bp
from copilot_core.api.v1.graph import bp as graph_bp
from copilot_core.api.v1.habitus import bp as habitus_bp
from copilot_core.api.v1.habitus_dashboard_cards import bp as dashboard_cards_bp
from copilot_core.api.v1.graph_ops import bp as graph_ops_bp
from copilot_core.api.v1.vector import bp as vector_bp
from copilot_core.api.v1.neurons import bp as neurons_bp
from copilot_core.api.v1.weather import bp as weather_bp
from copilot_core.api.v1.voice_context_bp import bp as voice_context_bp
from copilot_core.api.v1.swagger_ui import bp as swagger_ui_bp
from copilot_core.api.v1.user_preferences import bp as user_preferences_bp
from copilot_core.api.v1.dashboard import bp as dashboard_bp
from copilot_core.knowledge_graph.api import bp as knowledge_graph_bp

# New feature APIs
from copilot_core.api.v1.search import bp as search_bp
from copilot_core.api.v1.notifications import bp as notifications_bp
from copilot_core.api.v1.user_hints import bp as user_hints_bp
from copilot_core.api.v1.conversation import conversation_bp

# Phase 5: Cross-Home Sync and Collective Intelligence
from copilot_core.sharing.api import sharing_bp
from copilot_core.collective_intelligence.api import federated_bp

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# Register sub-blueprints with relative url_prefix (e.g. /neurons, /kg)
# These are correctly nested under /api/v1
api_v1.register_blueprint(dev_bp)
api_v1.register_blueprint(events_bp)
api_v1.register_blueprint(candidates_bp)
api_v1.register_blueprint(mood_bp)
api_v1.register_blueprint(graph_bp)
api_v1.register_blueprint(habitus_bp)
api_v1.register_blueprint(dashboard_cards_bp)
api_v1.register_blueprint(graph_ops_bp)
api_v1.register_blueprint(vector_bp)
api_v1.register_blueprint(neurons_bp)
api_v1.register_blueprint(weather_bp)
api_v1.register_blueprint(voice_context_bp)
api_v1.register_blueprint(swagger_ui_bp)
api_v1.register_blueprint(user_preferences_bp)
api_v1.register_blueprint(dashboard_bp)
api_v1.register_blueprint(knowledge_graph_bp)

# Register new feature APIs
api_v1.register_blueprint(search_bp)
api_v1.register_blueprint(notifications_bp)
api_v1.register_blueprint(user_hints_bp)

# Extended OpenAI Conversation support
api_v1.register_blueprint(conversation_bp)

# Register Phase 5 APIs
api_v1.register_blueprint(sharing_bp)
api_v1.register_blueprint(federated_bp)

# Note: Standalone blueprints with absolute prefixes (/api/v1/...)
# are registered directly on the app via core_setup.register_blueprints():
# - energy_bp, unifi_bp, system_health_bp, tags_bp,
#   brain_graph_bp, habitus_bp, candidates_bp, mood_bp, dev_surface_bp
# They must NOT be nested under api_v1 to avoid double /api/v1/api/v1/ prefixes.
