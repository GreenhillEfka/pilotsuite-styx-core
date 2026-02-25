from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nextcloud_bp = Blueprint("nextcloud", __name__, url_prefix="/api/v1/nextcloud")
@nextcloud_bp.route("", methods=["GET"])
@require_token
def nextcloud(): return jsonify({"ok": True})
