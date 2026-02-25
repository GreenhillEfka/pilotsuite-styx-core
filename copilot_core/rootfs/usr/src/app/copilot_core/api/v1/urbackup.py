from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
urbackup_bp = Blueprint("urbackup", __name__, url_prefix="/api/v1/urbackup")
@urbackup_bp.route("", methods=["GET"])
@require_token
def urbackup(): return jsonify({"ok": True})
