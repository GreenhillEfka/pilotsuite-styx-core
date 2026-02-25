from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wasabi2_bp = Blueprint("wasabi2", __name__, url_prefix="/api/v1/wasabi2")
@wasabi2_bp.route("", methods=["GET"])
@require_token
def wasabi2(): return jsonify({"ok": True})
