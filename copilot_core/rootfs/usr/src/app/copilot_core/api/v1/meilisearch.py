from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
meilisearch_bp = Blueprint("meilisearch", __name__, url_prefix="/api/v1/meilisearch")
@meilisearch_bp.route("", methods=["GET"])
@require_token
def meilisearch(): return jsonify({"ok": True})
