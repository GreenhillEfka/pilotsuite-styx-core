from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
download_bp = Blueprint("download", __name__, url_prefix="/api/v1/download")
@download_bp.route("", methods=["GET"])
@require_token
def download(): return jsonify({"ok": True})
