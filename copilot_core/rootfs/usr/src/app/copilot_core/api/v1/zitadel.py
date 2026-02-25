from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zitadel_bp = Blueprint("zitadel", __name__, url_prefix="/api/v1/zitadel")
@zitadel_bp.route("", methods=["GET"])
@require_token
def zitadel(): return jsonify({"ok": True})
