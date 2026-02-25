from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
durables_bp = Blueprint("durables", __name__, url_prefix="/api/v1/durables")
@durables_bp.route("", methods=["GET"])
@require_token
def durables(): return jsonify({"ok": True})
