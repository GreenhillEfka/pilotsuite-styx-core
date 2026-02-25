from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lightfull_bp = Blueprint("lightfull", __name__, url_prefix="/api/v1/lightfull")
@lightfull_bp.route("", methods=["GET"])
@require_token
def lightfull(): return jsonify({"ok": True})
