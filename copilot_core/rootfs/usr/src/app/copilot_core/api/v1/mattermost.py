from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mattermost_bp = Blueprint("mattermost", __name__, url_prefix="/api/v1/mattermost")
@mattermost_bp.route("", methods=["GET"])
@require_token
def mattermost(): return jsonify({"ok": True})
