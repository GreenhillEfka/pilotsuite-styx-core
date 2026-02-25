from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kerberos_bp = Blueprint("kerberos", __name__, url_prefix="/api/v1/kerberos")
@kerberos_bp.route("", methods=["GET"])
@require_token
def kerberos(): return jsonify({"ok": True})
