from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
deltalake_bp = Blueprint("deltalake", __name__, url_prefix="/api/v1/deltalake")
@deltalake_bp.route("", methods=["GET"])
@require_token
def deltalake(): return jsonify({"ok": True})
