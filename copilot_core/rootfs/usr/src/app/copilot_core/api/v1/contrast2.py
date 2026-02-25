from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
contrast2_bp = Blueprint("contrast2", __name__, url_prefix="/api/v1/contrast2")
@contrast2_bp.route("", methods=["GET"])
@require_token
def contrast2(): return jsonify({"ok": True})
