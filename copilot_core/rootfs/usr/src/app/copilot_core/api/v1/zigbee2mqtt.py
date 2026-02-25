from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zigbee2mqtt_bp = Blueprint("zigbee2mqtt", __name__, url_prefix="/api/v1/zigbee2mqtt")
@zigbee2mqtt_bp.route("", methods=["GET"])
@require_token
def zigbee2mqtt(): return jsonify({"ok": True})
