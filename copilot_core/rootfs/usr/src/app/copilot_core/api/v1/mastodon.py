from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mastodon_bp = Blueprint("mastodon", __name__, url_prefix="/api/v1/mastodon")
@mastodon_bp.route("", methods=["GET"])
@require_token
def mastodon(): return jsonify({"ok": True})
