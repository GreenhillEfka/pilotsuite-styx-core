from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
alicloud_bp = Blueprint("alicloud", __name__, url_prefix="/api/v1/alicloud")
@alicloud_bp.route("", methods=["GET"])
@require_token
def alicloud(): return jsonify({"ok": True})
