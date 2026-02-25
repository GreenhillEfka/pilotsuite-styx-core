from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scaleway_bp = Blueprint("scaleway2", __name__, url_prefix="/api/v1/scaleway2")
@scaleway_bp.route("", methods=["GET"])
@require_token
def scaleway2(): return jsonify({"ok": True})
