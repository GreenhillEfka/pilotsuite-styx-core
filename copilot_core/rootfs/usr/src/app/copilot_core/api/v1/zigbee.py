from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zigbee_bp = Blueprint("zigbee", __name__, url_prefix="/api/v1/zigbee")
@zigbee_bp.route("", methods=["GET"])
@require_token
def zigbee(): return jsonify({"ok": True})
