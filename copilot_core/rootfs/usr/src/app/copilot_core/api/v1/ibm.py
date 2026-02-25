from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ibm_bp = Blueprint("ibm", __name__, url_prefix="/api/v1/ibm")
@ibm_bp.route("", methods=["GET"])
@require_token
def ibm(): return jsonify({"ok": True})
