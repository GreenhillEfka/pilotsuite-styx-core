from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zwavejs_bp = Blueprint("zwavejs", __name__, url_prefix="/api/v1/zwavejs")
@zwavejs_bp.route("", methods=["GET"])
@require_token
def zwavejs(): return jsonify({"ok": True})
