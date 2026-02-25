from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
groovy_bp = Blueprint("groovy", __name__, url_prefix="/api/v1/groovy")
@groovy_bp.route("", methods=["GET"])
@require_token
def groovy(): return jsonify({"ok": True})
