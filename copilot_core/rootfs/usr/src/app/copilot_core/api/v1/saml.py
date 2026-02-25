from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
saml_bp = Blueprint("saml", __name__, url_prefix="/api/v1/saml")
@saml_bp.route("", methods=["GET"])
@require_token
def saml(): return jsonify({"ok": True})
