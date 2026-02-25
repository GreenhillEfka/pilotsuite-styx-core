from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pon_bp = Blueprint("pon", __name__, url_prefix="/api/v1/pon")
@pon_bp.route("", methods=["GET"])
@require_token
def pon(): return jsonify({"ok": True})
