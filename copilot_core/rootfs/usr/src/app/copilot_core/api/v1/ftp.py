from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ftp_bp = Blueprint("ftp", __name__, url_prefix="/api/v1/ftp")
@ftp_bp.route("", methods=["GET"])
@require_token
def ftp(): return jsonify({"ok": True})
