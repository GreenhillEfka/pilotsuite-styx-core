from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
shynet_bp = Blueprint("shynet", __name__, url_prefix="/api/v1/shynet")
@shynet_bp.route("", methods=["GET"])
@require_token
def shynet(): return jsonify({"ok": True})
