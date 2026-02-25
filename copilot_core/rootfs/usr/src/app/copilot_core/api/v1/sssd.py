from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sssd_bp = Blueprint("sssd", __name__, url_prefix="/api/v1/sssd")
@sssd_bp.route("", methods=["GET"])
@require_token
def sssd(): return jsonify({"ok": True})
