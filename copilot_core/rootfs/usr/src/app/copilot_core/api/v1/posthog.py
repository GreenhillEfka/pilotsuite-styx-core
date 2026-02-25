from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
posthog_bp = Blueprint("posthog", __name__, url_prefix="/api/v1/posthog")
@posthog_bp.route("", methods=["GET"])
@require_token
def posthog(): return jsonify({"ok": True})
