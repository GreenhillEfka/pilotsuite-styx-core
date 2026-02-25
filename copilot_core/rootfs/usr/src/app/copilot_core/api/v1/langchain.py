from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
langchain_bp = Blueprint("langchain", __name__, url_prefix="/api/v1/langchain")
@langchain_bp.route("", methods=["GET"])
@require_token
def langchain(): return jsonify({"ok": True})
