from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
owncloud_bp = Blueprint("owncloud", __name__, url_prefix="/api/v1/owncloud")
@owncloud_bp.route("", methods=["GET"])
@require_token
def owncloud(): return jsonify({"ok": True})
