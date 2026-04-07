"""
Standalone Web UI for PilotSuite Core.

Flask-based dashboard for non-HA users.
"""
from __future__ import annotations
import logging
from flask import Flask, render_template, jsonify, request, redirect, url_for
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# App configuration
STATIC_PATH = Path(__file__).parent / "static"
TEMPLATES_PATH = Path(__file__).parent / "templates"

app = Flask(__name__, static_folder=str(STATIC_PATH), template_folder=str(TEMPLATES_PATH))


@app.route("/")
def index():
    """Main dashboard."""
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """Get system status."""
    return jsonify({
        "status": "online",
        "version": "1.0.0-rc2",
        "modules": {
            "database": "ok",
            "tasks": "ok",
            "analytics": "ok",
            "calendar": "ok",
            "notifications": "ok",
        }
    })


@app.route("/api/dashboard")
def api_dashboard():
    """Get dashboard data."""
    return jsonify({
        "kpi": {
            "total_events": 0,
            "presence_events": 0,
            "patterns_learned": 0,
            "energy_savings": 0.0,
        },
        "modules": [],
        "alerts": [],
    })


def create_app() -> Flask:
    """Create and configure the Flask app."""
    app.config["SECRET_KEY"] = "pilotsuite-secret-key-change-in-production"
    return app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


__all__ = ["app", "create_app"]
