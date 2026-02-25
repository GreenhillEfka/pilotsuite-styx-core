from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dsl_bp = Blueprint("dsl", __name__, url_prefix="/api/v1/dsl")
@dsl_bp.route("", methods=["GET"])
@require_token
def dsl(): return jsonify({"ok": True})
