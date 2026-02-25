from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gptq_bp = Blueprint("gptq", __name__, url_prefix="/api/v1/gptq")
@gptq_bp.route("", methods=["GET"])
@require_token
def gptq(): return jsonify({"ok": True})
