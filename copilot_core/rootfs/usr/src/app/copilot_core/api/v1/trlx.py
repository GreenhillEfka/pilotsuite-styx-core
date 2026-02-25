from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
trlx_bp = Blueprint("trlx", __name__, url_prefix="/api/v1/trlx")
@trlx_bp.route("", methods=["GET"])
@require_token
def trlx(): return jsonify({"ok": True})
