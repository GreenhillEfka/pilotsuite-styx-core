from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
npm_bp = Blueprint("npm", __name__, url_prefix="/api/v1/npm")
@npm_bp.route("", methods=["GET"])
@require_token
def npm(): return jsonify({"ok": True})
