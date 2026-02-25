from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
backblaze_bp = Blueprint("backblaze", __name__, url_prefix="/api/v1/backblaze")
@backblaze_bp.route("", methods=["GET"])
@require_token
def backblaze(): return jsonify({"ok": True})
