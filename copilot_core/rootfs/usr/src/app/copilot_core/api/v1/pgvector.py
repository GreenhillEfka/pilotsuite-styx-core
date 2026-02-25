from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pgvector_bp = Blueprint("pgvector", __name__, url_prefix="/api/v1/pgvector")
@pgvector_bp.route("", methods=["GET"])
@require_token
def pgvector(): return jsonify({"ok": True})
