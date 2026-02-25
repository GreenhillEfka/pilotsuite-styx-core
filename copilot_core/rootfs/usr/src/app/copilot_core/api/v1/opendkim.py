from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
opendkim_bp = Blueprint("opendkim", __name__, url_prefix="/api/v1/opendkim")
@opendkim_bp.route("", methods=["GET"])
@require_token
def opendkim(): return jsonify({"ok": True})
