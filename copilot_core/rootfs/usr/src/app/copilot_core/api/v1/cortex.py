from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cortex_bp = Blueprint("cortex", __name__, url_prefix="/api/v1/cortex")
@cortex_bp.route("", methods=["GET"])
@require_token
def cortex(): return jsonify({"ok": True})
