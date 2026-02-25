from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
accelerate_bp = Blueprint("accelerate", __name__, url_prefix="/api/v1/accelerate")
@accelerate_bp.route("", methods=["GET"])
@require_token
def accelerate(): return jsonify({"ok": True})
