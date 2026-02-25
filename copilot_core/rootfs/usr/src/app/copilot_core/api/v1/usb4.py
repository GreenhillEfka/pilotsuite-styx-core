from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
usb4_bp = Blueprint("usb4", __name__, url_prefix="/api/v1/usb4")
@usb4_bp.route("", methods=["GET"])
@require_token
def usb4(): return jsonify({"ok": True})
