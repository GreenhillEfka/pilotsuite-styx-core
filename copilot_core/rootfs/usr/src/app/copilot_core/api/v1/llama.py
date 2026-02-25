from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
llama_bp = Blueprint("llama", __name__, url_prefix="/api/v1/llama")
@llama_bp.route("", methods=["GET"])
@require_token
def llama(): return jsonify({"ok": True})
