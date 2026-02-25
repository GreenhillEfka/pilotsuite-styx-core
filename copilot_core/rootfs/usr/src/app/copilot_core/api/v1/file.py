from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
file_bp = Blueprint("file", __name__, url_prefix="/api/v1/file")
@file_bp.route("", methods=["GET"])
@require_token
def file(): return jsonify({"ok": True})
