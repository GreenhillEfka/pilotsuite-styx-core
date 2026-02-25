from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
uwb_bp = Blueprint("uwb", __name__, url_prefix="/api/v1/uwb")
@uwb_bp.route("", methods=["GET"])
@require_token
def uwb(): return jsonify({"ok": True})
