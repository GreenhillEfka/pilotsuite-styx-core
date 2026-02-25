from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
solusvm_bp = Blueprint("solusvm", __name__, url_prefix="/api/v1/solusvm")
@solusvm_bp.route("", methods=["GET"])
@require_token
def solusvm(): return jsonify({"ok": True})
