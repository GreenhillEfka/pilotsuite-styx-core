from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
jekyll_bp = Blueprint("jekyll", __name__, url_prefix="/api/v1/jekyll")
@jekyll_bp.route("", methods=["GET"])
@require_token
def jekyll(): return jsonify({"ok": True})
