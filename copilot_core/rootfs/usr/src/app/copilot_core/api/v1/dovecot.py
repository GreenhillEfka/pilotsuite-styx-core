from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dovecot_bp = Blueprint("dovecot", __name__, url_prefix="/api/v1/dovecot")
@dovecot_bp.route("", methods=["GET"])
@require_token
def dovecot(): return jsonify({"ok": True})
