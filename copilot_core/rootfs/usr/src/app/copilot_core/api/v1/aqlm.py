from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
aqlm_bp = Blueprint("aqlm", __name__, url_prefix="/api/v1/aqlm")
@aqlm_bp.route("", methods=["GET"])
@require_token
def aqlm(): return jsonify({"ok": True})
