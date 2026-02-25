from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
assemblyscript_bp = Blueprint("assemblyscript", __name__, url_prefix="/api/v1/assemblyscript")
@assemblyscript_bp.route("", methods=["GET"])
@require_token
def assemblyscript(): return jsonify({"ok": True})
