from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mixpanel_bp = Blueprint("mixpanel", __name__, url_prefix="/api/v1/mixpanel")
@mixpanel_bp.route("", methods=["GET"])
@require_token
def mixpanel(): return jsonify({"ok": True})
