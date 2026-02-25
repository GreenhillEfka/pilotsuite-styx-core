from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mailu_bp = Blueprint("mailu", __name__, url_prefix="/api/v1/mailu")
@mailu_bp.route("", methods=["GET"])
@require_token
def mailu(): return jsonify({"ok": True})
