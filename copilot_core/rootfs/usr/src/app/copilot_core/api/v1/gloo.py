from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gloo_bp = Blueprint("gloo", __name__, url_prefix="/api/v1/gloo")
@gloo_bp.route("", methods=["GET"])
@require_token
def gloo(): return jsonify({"ok": True})
