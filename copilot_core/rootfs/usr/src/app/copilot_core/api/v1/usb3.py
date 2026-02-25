from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
usb3_bp = Blueprint("usb3", __name__, url_prefix="/api/v1/usb3")
@usb3_bp.route("", methods=["GET"])
@require_token
def usb3(): return jsonify({"ok": True})
