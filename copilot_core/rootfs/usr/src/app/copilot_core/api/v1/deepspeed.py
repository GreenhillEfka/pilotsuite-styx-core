from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
deepspeed_bp = Blueprint("deepspeed", __name__, url_prefix="/api/v1/deepspeed")
@deepspeed_bp.route("", methods=["GET"])
@require_token
def deepspeed(): return jsonify({"ok": True})
