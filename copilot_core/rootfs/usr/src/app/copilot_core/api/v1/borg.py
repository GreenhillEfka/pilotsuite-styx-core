from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
borg_bp = Blueprint("borg", __name__, url_prefix="/api/v1/borg")
@borg_bp.route("", methods=["GET"])
@require_token
def borg(): return jsonify({"ok": True})
