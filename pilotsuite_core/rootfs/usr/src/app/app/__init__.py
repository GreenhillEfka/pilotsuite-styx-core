"""Main app entry point and routing."""
from flask import Flask, jsonify

from app.routes.debug import bp as debug_bp
from copilot_core import services
from copilot_core.context import Context
from copilot_core.debug import get_debug

app = Flask(__name__)

# Register blueprints
app.register_blueprint(debug_bp)


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "ok",
            "debug_mode": get_debug(),
            "timestamp": services.get_timestamp(),
        }
    ), 200


@app.route("/version")
def version():
    """Version info endpoint."""
    return jsonify(
        {
            "version": services.get_version(),
            "debug_mode": get_debug(),
        }
    ), 200


@app.route("/api/v1/capabilities")
def capabilities():
    """API capabilities."""
    return jsonify(
        {
            "version": "v1",
            "debug_mode": get_debug(),
            "modules": ["habitus", "tags2", "unifi", "energy", "system-health"],
            "brain_graph": {"feeding_enabled": True, "bounded": True},
        }
    ), 200


@app.route("/api/v1/debug")
def debug_status():
    """Debug mode status (legacy)."""
    return jsonify({"debug_mode": get_debug()}), 200


@app.route("/api/v1/events", methods=["POST"])
def events():
    """Event ingest endpoint."""
    ctx = Context()
    return jsonify({"ingested": 0, "debug_mode": get_debug()}), 200


@app.route("/api/v1/events", methods=["GET"])
def events_get():
    """Debug: get recent events."""
    return jsonify({"events": [], "debug_mode": get_debug()}), 200
