from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
authentik_bp = Blueprint("authentik", __name__, url_prefix="/api/v1/authentik")
@authentik_bp.route("", methods=["GET"])
@require_token
def authentik(): return jsonify({"ok": True})
