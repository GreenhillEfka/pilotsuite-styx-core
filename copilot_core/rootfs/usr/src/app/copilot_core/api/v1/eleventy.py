from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
eleventy_bp = Blueprint("eleventy", __name__, url_prefix="/api/v1/eleventy")
@eleventy_bp.route("", methods=["GET"])
@require_token
def eleventy(): return jsonify({"ok": True})
