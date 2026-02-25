from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
weaviate_bp = Blueprint("weaviate", __name__, url_prefix="/api/v1/weaviate")
@weaviate_bp.route("", methods=["GET"])
@require_token
def weaviate(): return jsonify({"ok": True})
