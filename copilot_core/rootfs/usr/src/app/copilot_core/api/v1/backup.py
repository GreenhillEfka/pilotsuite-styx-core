from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
backup_bp = Blueprint("backup", __name__, url_prefix="/api/v1/backup")
@backup_bp.route("", methods=["GET"])
@require_token
def backup(): return jsonify({"ok": True})
