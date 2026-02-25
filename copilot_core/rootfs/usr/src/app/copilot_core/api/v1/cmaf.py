from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cmaf_bp = Blueprint("cmaf", __name__, url_prefix="/api/v1/cmaf")
@cmaf_bp.route("", methods=["GET"])
@require_token
def cmaf(): return jsonify({"ok": True})
