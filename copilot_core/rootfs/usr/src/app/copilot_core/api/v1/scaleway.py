from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scaleway_bp = Blueprint("scaleway", __name__, url_prefix="/api/v1/scaleway")
@scaleway_bp.route("", methods=["GET"])
@require_token
def scaleway(): return jsonify({"ok": True})
