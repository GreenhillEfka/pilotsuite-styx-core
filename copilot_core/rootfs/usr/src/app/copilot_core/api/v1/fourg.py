from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fourg_bp = Blueprint("fourg", __name__, url_prefix="/api/v1/fourg")
@fourg_bp.route("", methods=["GET"])
@require_token
def fourg(): return jsonify({"ok": True})
