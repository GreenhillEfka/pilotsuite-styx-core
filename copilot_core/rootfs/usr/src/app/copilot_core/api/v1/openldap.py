from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
openldap_bp = Blueprint("openldap", __name__, url_prefix="/api/v1/openldap")
@openldap_bp.route("", methods=["GET"])
@require_token
def openldap(): return jsonify({"ok": True})
