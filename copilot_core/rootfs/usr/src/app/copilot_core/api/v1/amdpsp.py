from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
amdpsp_bp = Blueprint("amdpsp", __name__, url_prefix="/api/v1/amdpsp")
@amdpsp_bp.route("", methods=["GET"])
@require_token
def amdpsp(): return jsonify({"ok": True})
