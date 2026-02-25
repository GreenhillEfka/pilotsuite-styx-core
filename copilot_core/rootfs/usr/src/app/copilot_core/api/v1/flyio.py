from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
flyio_bp = Blueprint("flyio", __name__, url_prefix="/api/v1/flyio")
@flyio_bp.route("", methods=["GET"])
@require_token
def flyio(): return jsonify({"ok": True})
