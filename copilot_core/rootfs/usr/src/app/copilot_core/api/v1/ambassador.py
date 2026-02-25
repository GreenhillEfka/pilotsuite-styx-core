from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ambassador_bp = Blueprint("ambassador", __name__, url_prefix="/api/v1/ambassador")
@ambassador_bp.route("", methods=["GET"])
@require_token
def ambassador(): return jsonify({"ok": True})
