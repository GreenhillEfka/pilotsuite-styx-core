from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
apisix_bp = Blueprint("apisix", __name__, url_prefix="/api/v1/apisix")
@apisix_bp.route("", methods=["GET"])
@require_token
def apisix(): return jsonify({"ok": True})
