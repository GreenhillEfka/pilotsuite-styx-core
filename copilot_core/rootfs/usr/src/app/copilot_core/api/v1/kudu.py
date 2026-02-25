from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kudu_bp = Blueprint("kudu", __name__, url_prefix="/api/v1/kudu")
@kudu_bp.route("", methods=["GET"])
@require_token
def kudu(): return jsonify({"ok": True})
