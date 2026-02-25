from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
seafile_bp = Blueprint("seafile", __name__, url_prefix="/api/v1/seafile")
@seafile_bp.route("", methods=["GET"])
@require_token
def seafile(): return jsonify({"ok": True})
