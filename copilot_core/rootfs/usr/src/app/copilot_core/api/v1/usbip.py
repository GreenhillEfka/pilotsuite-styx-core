from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
usbip_bp = Blueprint("usbip", __name__, url_prefix="/api/v1/usbip")
@usbip_bp.route("", methods=["GET"])
@require_token
def usbip(): return jsonify({"ok": True})
