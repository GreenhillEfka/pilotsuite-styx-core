from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pam_bp = Blueprint("pam", __name__, url_prefix="/api/v1/pam")
@pam_bp.route("", methods=["GET"])
@require_token
def pam(): return jsonify({"ok": True})
