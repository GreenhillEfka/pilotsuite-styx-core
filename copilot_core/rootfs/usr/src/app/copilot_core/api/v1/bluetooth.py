"""
Bluetooth API - PilotSuite v7.41
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

bluetooth_bp = Blueprint("bluetooth", __name__, url_prefix="/api/v1/bluetooth")

@bluetooth_bp.route("", methods=["GET"])
@require_token
def bluetooth_status():
    return jsonify({"ok": True, "adapters": []})
