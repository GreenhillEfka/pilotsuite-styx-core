from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
remix_bp = Blueprint("remix", __name__, url_prefix="/api/v1/remix")
@remix_bp.route("", methods=["GET"])
@require_token
def remix(): return jsonify({"ok": True})
