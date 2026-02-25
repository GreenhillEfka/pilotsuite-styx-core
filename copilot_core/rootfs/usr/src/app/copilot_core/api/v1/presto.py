from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
presto_bp = Blueprint("presto", __name__, url_prefix="/api/v1/presto")
@presto_bp.route("", methods=["GET"])
@require_token
def presto(): return jsonify({"ok": True})
