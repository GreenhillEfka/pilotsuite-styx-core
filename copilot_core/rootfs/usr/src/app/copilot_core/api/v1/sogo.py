from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sogo_bp = Blueprint("sogo", __name__, url_prefix="/api/v1/sogo")
@sogo_bp.route("", methods=["GET"])
@require_token
def sogo(): return jsonify({"ok": True})
