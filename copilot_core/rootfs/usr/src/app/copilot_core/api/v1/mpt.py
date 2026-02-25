from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mpt_bp = Blueprint("mpt", __name__, url_prefix="/api/v1/mpt")
@mpt_bp.route("", methods=["GET"])
@require_token
def mpt(): return jsonify({"ok": True})
