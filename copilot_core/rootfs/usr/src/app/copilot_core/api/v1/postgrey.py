from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
postgrey_bp = Blueprint("postgrey", __name__, url_prefix="/api/v1/postgrey")
@postgrey_bp.route("", methods=["GET"])
@require_token
def postgrey(): return jsonify({"ok": True})
