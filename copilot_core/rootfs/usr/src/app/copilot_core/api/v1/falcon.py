from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
falcon_bp = Blueprint("falcon", __name__, url_prefix="/api/v1/falcon")
@falcon_bp.route("", methods=["GET"])
@require_token
def falcon(): return jsonify({"ok": True})
