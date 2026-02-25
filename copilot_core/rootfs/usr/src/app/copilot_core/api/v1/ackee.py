from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ackee_bp = Blueprint("ackee", __name__, url_prefix="/api/v1/ackee")
@ackee_bp.route("", methods=["GET"])
@require_token
def ackee(): return jsonify({"ok": True})
