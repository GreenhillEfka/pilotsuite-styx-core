from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nifi_bp = Blueprint("nifi", __name__, url_prefix="/api/v1/nifi")
@nifi_bp.route("", methods=["GET"])
@require_token
def nifi(): return jsonify({"ok": True})
