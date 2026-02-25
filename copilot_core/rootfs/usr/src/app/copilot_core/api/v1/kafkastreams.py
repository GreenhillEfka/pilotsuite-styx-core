from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kafkastreams_bp = Blueprint("kafkastreams", __name__, url_prefix="/api/v1/kafkastreams")
@kafkastreams_bp.route("", methods=["GET"])
@require_token
def kafkastreams(): return jsonify({"ok": True})
