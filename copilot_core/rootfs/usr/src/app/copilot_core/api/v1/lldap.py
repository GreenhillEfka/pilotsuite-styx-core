from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lldap_bp = Blueprint("lldap", __name__, url_prefix="/api/v1/lldap")
@lldap_bp.route("", methods=["GET"])
@require_token
def lldap(): return jsonify({"ok": True})
