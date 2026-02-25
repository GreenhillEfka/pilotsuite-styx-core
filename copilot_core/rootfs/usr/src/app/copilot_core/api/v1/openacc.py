from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
openacc_bp = Blueprint("openacc", __name__, url_prefix="/api/v1/openacc")
@openacc_bp.route("", methods=["GET"])
@require_token
def openacc(): return jsonify({"ok": True})
