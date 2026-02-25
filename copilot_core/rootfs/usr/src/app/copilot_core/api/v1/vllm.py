from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vllm_bp = Blueprint("vllm", __name__, url_prefix="/api/v1/vllm")
@vllm_bp.route("", methods=["GET"])
@require_token
def vllm(): return jsonify({"ok": True})
