from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
archive_bp = Blueprint("archive", __name__, url_prefix="/api/v1/archive")
@archive_bp.route("", methods=["GET"])
@require_token
def archive(): return jsonify({"ok": True})
