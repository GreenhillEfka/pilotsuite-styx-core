from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pinecone_bp = Blueprint("pinecone", __name__, url_prefix="/api/v1/pinecone")
@pinecone_bp.route("", methods=["GET"])
@require_token
def pinecone(): return jsonify({"ok": True})
