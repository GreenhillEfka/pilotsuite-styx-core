from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
filestash_bp = Blueprint("filestash", __name__, url_prefix="/api/v1/filestash")
@filestash_bp.route("", methods=["GET"])
@require_token
def filestash(): return jsonify({"ok": True})
