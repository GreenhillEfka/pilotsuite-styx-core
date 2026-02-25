from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifitdls_bp = Blueprint("wifitdls", __name__, url_prefix="/api/v1/wifitdls")
@wifitdls_bp.route("", methods=["GET"])
@require_token
def wifitdls(): return jsonify({"ok": True})
