from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
odin_bp = Blueprint("odin", __name__, url_prefix="/api/v1/odin")
@odin_bp.route("", methods=["GET"])
@require_token
def odin(): return jsonify({"ok": True})
