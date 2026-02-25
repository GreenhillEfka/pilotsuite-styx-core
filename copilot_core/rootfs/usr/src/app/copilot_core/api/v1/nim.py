from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nim_bp = Blueprint("nim", __name__, url_prefix="/api/v1/nim")
@nim_bp.route("", methods=["GET"])
@require_token
def nim(): return jsonify({"ok": True})
