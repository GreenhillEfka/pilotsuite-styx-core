from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
spaces_bp = Blueprint("spaces", __name__, url_prefix="/api/v1/spaces")
@spaces_bp.route("", methods=["GET"])
@require_token
def spaces(): return jsonify({"ok": True})
