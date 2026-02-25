from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
thread12_bp = Blueprint("thread12", __name__, url_prefix="/api/v1/thread12")
@thread12_bp.route("", methods=["GET"])
@require_token
def thread12(): return jsonify({"ok": True})
