from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
clamav_bp = Blueprint("clamav", __name__, url_prefix="/api/v1/clamav")
@clamav_bp.route("", methods=["GET"])
@require_token
def clamav(): return jsonify({"ok": True})
