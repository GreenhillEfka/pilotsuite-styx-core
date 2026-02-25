from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ldap_bp = Blueprint("ldap", __name__, url_prefix="/api/v1/ldap")
@ldap_bp.route("", methods=["GET"])
@require_token
def ldap(): return jsonify({"ok": True})
