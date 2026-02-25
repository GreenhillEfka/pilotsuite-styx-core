from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dpo_bp = Blueprint("dpo", __name__, url_prefix="/api/v1/dpo")
@dpo_bp.route("", methods=["GET"])
@require_token
def dpo(): return jsonify({"ok": True})
