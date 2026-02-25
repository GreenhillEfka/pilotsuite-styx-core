from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tfcloud_bp = Blueprint("tfcloud", __name__, url_prefix="/api/v1/tfcloud")
@tfcloud_bp.route("", methods=["GET"])
@require_token
def tfcloud(): return jsonify({"ok": True})
