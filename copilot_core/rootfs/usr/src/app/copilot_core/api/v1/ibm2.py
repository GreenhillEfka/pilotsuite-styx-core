from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ibmbp = Blueprint("ibm2", __name__, url_prefix="/api/v1/ibm2")
@ibmbp.route("", methods=["GET"])
@require_token
def ibm2(): return jsonify({"ok": True})
