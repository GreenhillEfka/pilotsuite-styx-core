from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
upload_bp = Blueprint("upload", __name__, url_prefix="/api/v1/upload")
@upload_bp.route("", methods=["GET"])
@require_token
def upload(): return jsonify({"ok": True})
