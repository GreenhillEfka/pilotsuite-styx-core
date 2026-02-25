from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
consulconnect_bp = Blueprint("consulconnect", __name__, url_prefix="/api/v1/consulconnect")
@consulconnect_bp.route("", methods=["GET"])
@require_token
def consulconnect(): return jsonify({"ok": True})
