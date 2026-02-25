from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bunny_bp = Blueprint("bunny", __name__, url_prefix="/api/v1/bunny")
@bunny_bp.route("", methods=["GET"])
@require_token
def bunny(): return jsonify({"ok": True})
