from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sdcard_bp = Blueprint("sdcard", __name__, url_prefix="/api/v1/sdcard")
@sdcard_bp.route("", methods=["GET"])
@require_token
def sdcard(): return jsonify({"ok": True})
