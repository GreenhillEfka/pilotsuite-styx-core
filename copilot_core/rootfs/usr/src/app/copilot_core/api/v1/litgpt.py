from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
litgpt_bp = Blueprint("litgpt", __name__, url_prefix="/api/v1/litgpt")
@litgpt_bp.route("", methods=["GET"])
@require_token
def litgpt(): return jsonify({"ok": True})
