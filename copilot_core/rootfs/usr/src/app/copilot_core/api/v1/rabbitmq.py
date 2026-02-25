from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rabbitmq_bp = Blueprint("rabbitmq", __name__, url_prefix="/api/v1/rabbitmq")
@rabbitmq_bp.route("", methods=["GET"])
@require_token
def rabbitmq(): return jsonify({"ok": True})
