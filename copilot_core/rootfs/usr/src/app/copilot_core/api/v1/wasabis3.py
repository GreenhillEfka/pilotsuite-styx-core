from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wasabis3_bp = Blueprint("wasabis3", __name__, url_prefix="/api/v1/wasabis3")
@wasabis3_bp.route("", methods=["GET"])
@require_token
def wasabis3(): return jsonify({"ok": True})
