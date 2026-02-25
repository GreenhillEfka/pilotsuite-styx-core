from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
restore_bp = Blueprint("restore", __name__, url_prefix="/api/v1/restore")
@restore_bp.route("", methods=["GET"])
@require_token
def restore(): return jsonify({"ok": True})
