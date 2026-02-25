from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
trench_bp = Blueprint("trench", __name__, url_prefix="/api/v1/trench")
@trench_bp.route("", methods=["GET"])
@require_token
def trench(): return jsonify({"ok": True})
