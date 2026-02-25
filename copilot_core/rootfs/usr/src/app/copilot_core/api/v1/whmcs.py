from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
whmcs_bp = Blueprint("whmcs", __name__, url_prefix="/api/v1/whmcs")
@whmcs_bp.route("", methods=["GET"])
@require_token
def whmcs(): return jsonify({"ok": True})
