from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
netlify_bp = Blueprint("netlify", __name__, url_prefix="/api/v1/netlify")
@netlify_bp.route("", methods=["GET"])
@require_token
def netlify(): return jsonify({"ok": True})
