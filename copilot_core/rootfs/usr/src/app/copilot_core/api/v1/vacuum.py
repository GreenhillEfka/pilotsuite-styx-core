from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vacuum_bp = Blueprint("vacuum", __name__, url_prefix="/api/v1/vacuum")
@vacuum_bp.route("", methods=["GET"])
@require_token
def vacuum(): return jsonify({"ok": True})
