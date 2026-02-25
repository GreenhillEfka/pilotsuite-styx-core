from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mpegdash_bp = Blueprint("mpegdash", __name__, url_prefix="/api/v1/mpegdash")
@mpegdash_bp.route("", methods=["GET"])
@require_token
def mpegdash(): return jsonify({"ok": True})
