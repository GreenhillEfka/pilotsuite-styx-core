from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cpp_bp = Blueprint("cpp", __name__, url_prefix="/api/v1/cpp")
@cpp_bp.route("", methods=["GET"])
@require_token
def cpp(): return jsonify({"ok": True})
