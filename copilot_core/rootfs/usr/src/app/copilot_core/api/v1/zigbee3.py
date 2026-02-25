from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zigbee3_bp = Blueprint("zigbee3", __name__, url_prefix="/api/v1/zigbee3")
@zigbee3_bp.route("", methods=["GET"])
@require_token
def zigbee3(): return jsonify({"ok": True})
