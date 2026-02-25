from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
spf_bp = Blueprint("spf", __name__, url_prefix="/api/v1/spf")
@spf_bp.route("", methods=["GET"])
@require_token
def spf(): return jsonify({"ok": True})
