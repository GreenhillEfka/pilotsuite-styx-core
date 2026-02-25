from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
denodeploy_bp = Blueprint("denodeploy", __name__, url_prefix="/api/v1/denodeploy")
@denodeploy_bp.route("", methods=["GET"])
@require_token
def denodeploy(): return jsonify({"ok": True})
