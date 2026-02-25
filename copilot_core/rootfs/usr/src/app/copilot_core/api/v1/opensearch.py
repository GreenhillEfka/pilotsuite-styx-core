from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
opensearch_bp = Blueprint("opensearch", __name__, url_prefix="/api/v1/opensearch")
@opensearch_bp.route("", methods=["GET"])
@require_token
def opensearch(): return jsonify({"ok": True})
