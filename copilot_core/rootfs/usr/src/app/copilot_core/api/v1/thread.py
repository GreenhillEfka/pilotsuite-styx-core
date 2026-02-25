from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
thread_bp = Blueprint("thread", __name__, url_prefix="/api/v1/thread")
@thread_bp.route("", methods=["GET"])
@require_token
def thread(): return jsonify({"ok": True})
