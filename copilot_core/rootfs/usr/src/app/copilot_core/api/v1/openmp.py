from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
openmp_bp = Blueprint("openmp", __name__, url_prefix="/api/v1/openmp")
@openmp_bp.route("", methods=["GET"])
@require_token
def openmp(): return jsonify({"ok": True})
