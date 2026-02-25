from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pulp_bp = Blueprint("pulp", __name__, url_prefix="/api/v1/pulp")
@pulp_bp.route("", methods=["GET"])
@require_token
def pulp(): return jsonify({"ok": True})
