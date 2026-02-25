from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
oidc_bp = Blueprint("oidc", __name__, url_prefix="/api/v1/oidc")
@oidc_bp.route("", methods=["GET"])
@require_token
def oidc(): return jsonify({"ok": True})
