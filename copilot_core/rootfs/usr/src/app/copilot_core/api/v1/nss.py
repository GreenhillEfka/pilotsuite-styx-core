from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nss_bp = Blueprint("nss", __name__, url_prefix="/api/v1/nss")
@nss_bp.route("", methods=["GET"])
@require_token
def nss(): return jsonify({"ok": True})
