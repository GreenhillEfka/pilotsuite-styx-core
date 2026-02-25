from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
restic_bp = Blueprint("restic", __name__, url_prefix="/api/v1/restic")
@restic_bp.route("", methods=["GET"])
@require_token
def restic(): return jsonify({"ok": True})
