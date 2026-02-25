from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
thread14_bp = Blueprint("thread14", __name__, url_prefix="/api/v1/thread14")
@thread14_bp.route("", methods=["GET"])
@require_token
def thread14(): return jsonify({"ok": True})
