from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
activemq_bp = Blueprint("activemq", __name__, url_prefix="/api/v1/activemq")
@activemq_bp.route("", methods=["GET"])
@require_token
def activemq(): return jsonify({"ok": True})
