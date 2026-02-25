from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
directory_bp = Blueprint("directory", __name__, url_prefix="/api/v1/directory")
@directory_bp.route("", methods=["GET"])
@require_token
def directory(): return jsonify({"ok": True})
