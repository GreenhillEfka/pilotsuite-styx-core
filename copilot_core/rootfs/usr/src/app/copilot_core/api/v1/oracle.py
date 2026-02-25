from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
oracle_bp = Blueprint("oracle", __name__, url_prefix="/api/v1/oracle")
@oracle_bp.route("", methods=["GET"])
@require_token
def oracle(): return jsonify({"ok": True})
