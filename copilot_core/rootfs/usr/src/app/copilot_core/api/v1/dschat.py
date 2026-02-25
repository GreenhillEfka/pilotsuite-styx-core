from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dschat_bp = Blueprint("dschat", __name__, url_prefix="/api/v1/dschat")
@dschat_bp.route("", methods=["GET"])
@require_token
def dschat(): return jsonify({"ok": True})
