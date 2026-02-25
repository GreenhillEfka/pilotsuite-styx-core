"""
USB API - PilotSuite v7.41
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

usb_bp = Blueprint("usb", __name__, url_prefix="/api/v1/usb")

@usb_bp.route("", methods=["GET"])
@require_token
def usb_devices():
    return jsonify({"ok": True, "devices": []})
