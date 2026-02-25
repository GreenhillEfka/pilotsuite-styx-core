from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ollama_bp = Blueprint("ollama", __name__, url_prefix="/api/v1/ollama")
@ollama_bp.route("", methods=["GET"])
@require_token
def ollama(): return jsonify({"ok": True})
