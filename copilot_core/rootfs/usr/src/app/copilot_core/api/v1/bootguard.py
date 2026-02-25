from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bootguard_bp = Blueprint("bootguard", __name__, url_prefix="/api/v1/bootguard")
@bootguard_bp.route("", methods=["GET"])
@require_token
def bootguard(): return jsonify({"ok": True})
