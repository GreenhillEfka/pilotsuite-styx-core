from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
susemgr_bp = Blueprint("susemgr", __name__, url_prefix="/api/v1/susemgr")
@susemgr_bp.route("", methods=["GET"])
@require_token
def susemgr(): return jsonify({"ok": True})
