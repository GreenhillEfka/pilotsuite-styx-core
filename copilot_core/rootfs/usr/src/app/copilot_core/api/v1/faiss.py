from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
faiss_bp = Blueprint("faiss", __name__, url_prefix="/api/v1/faiss")
@faiss_bp.route("", methods=["GET"])
@require_token
def faiss(): return jsonify({"ok": True})
