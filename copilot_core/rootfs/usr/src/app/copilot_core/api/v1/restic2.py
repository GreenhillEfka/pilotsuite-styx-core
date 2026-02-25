from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
restic2_bp = Blueprint("restic2", __name__, url_prefix="/api/v1/restic2")
@restic2_bp.route("", methods=["GET"])
@require_token
def restic2(): return jsonify({"ok": True})
