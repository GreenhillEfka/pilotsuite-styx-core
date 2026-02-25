from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
thread13_bp = Blueprint("thread13", __name__, url_prefix="/api/v1/thread13")
@thread13_bp.route("", methods=["GET"])
@require_token
def thread13(): return jsonify({"ok": True})
