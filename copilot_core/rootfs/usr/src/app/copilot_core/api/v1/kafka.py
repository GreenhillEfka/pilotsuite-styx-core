from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kafka_bp = Blueprint("kafka", __name__, url_prefix="/api/v1/kafka")
@kafka_bp.route("", methods=["GET"])
@require_token
def kafka(): return jsonify({"ok": True})
