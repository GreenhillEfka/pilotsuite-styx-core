from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kong_bp = Blueprint("kong", __name__, url_prefix="/api/v1/kong")
@kong_bp.route("", methods=["GET"])
@require_token
def kong(): return jsonify({"ok": True})
