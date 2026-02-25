from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
export_bp = Blueprint("export", __name__, url_prefix="/api/v1/export")
@export_bp.route("", methods=["GET"])
@require_token
def export(): return jsonify({"ok": True})
