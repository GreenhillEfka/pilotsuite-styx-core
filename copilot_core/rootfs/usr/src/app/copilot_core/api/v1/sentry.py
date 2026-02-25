from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sentry_bp = Blueprint("sentry", __name__, url_prefix="/api/v1/sentry")
@sentry_bp.route("", methods=["GET"])
@require_token
def sentry(): return jsonify({"ok": True})
