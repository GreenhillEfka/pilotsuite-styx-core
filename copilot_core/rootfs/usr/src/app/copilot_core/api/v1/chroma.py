from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
chroma_bp = Blueprint("chroma", __name__, url_prefix="/api/v1/chroma")
@chroma_bp.route("", methods=["GET"])
@require_token
def chroma(): return jsonify({"ok": True})
