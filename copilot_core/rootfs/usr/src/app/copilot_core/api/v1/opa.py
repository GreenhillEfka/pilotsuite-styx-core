from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
opa_bp = Blueprint("opa", __name__, url_prefix="/api/v1/opa")
@opa_bp.route("", methods=["GET"])
@require_token
def opa(): return jsonify({"ok": True})
