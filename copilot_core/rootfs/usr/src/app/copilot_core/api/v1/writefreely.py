from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
writefreely_bp = Blueprint("writefreely", __name__, url_prefix="/api/v1/writefreely")
@writefreely_bp.route("", methods=["GET"])
@require_token
def writefreely(): return jsonify({"ok": True})
