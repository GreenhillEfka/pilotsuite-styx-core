from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
do_bp = Blueprint("do", __name__, url_prefix="/api/v1/do")
@do_bp.route("", methods=["GET"])
@require_token
def do(): return jsonify({"ok": True})
