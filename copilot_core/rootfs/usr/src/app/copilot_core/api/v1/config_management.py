"""
Config Management API - PilotSuite v7.28.0
"""

from flask import Blueprint, jsonify, request
import logging
import os

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

config_bp = Blueprint("config", __name__, url_prefix="/api/v1/config")


@config_bp.route("", methods=["GET"])
@require_token
def get_config():
    """Get current config."""
    try:
        config_path = "/data/options.json"
        if os.path.exists(config_path):
            import json
            with open(config_path) as f:
                config = json.load(f)
            return jsonify({"ok": True, "config": config})
        return jsonify({"ok": True, "config": {}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@config_bp.route("", methods=["POST"])
@require_token
def update_config():
    """Update config."""
    data = request.get_json() or {}
    try:
        config_path = "/data/options.json"
        import json
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"ok": True, "message": "Config updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
