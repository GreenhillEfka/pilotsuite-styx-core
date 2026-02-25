from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
elasticsearch_bp = Blueprint("elasticsearch", __name__, url_prefix="/api/v1/elasticsearch")
@elasticsearch_bp.route("", methods=["GET"])
@require_token
def elasticsearch(): return jsonify({"ok": True})
