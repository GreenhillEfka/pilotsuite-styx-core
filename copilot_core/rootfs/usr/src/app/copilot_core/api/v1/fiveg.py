from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fiveg_bp = Blueprint("fiveg", __name__, url_prefix="/api/v1/fiveg")
@fiveg_bp.route("", methods=["GET"])
@require_token
def fiveg(): return jsonify({"ok": True})
