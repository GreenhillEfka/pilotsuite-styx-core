from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
matrix_bp = Blueprint("matrix", __name__, url_prefix="/api/v1/matrix")
@matrix_bp.route("", methods=["GET"])
@require_token
def matrix(): return jsonify({"ok": True})
