from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pulumi_bp = Blueprint("pulumi", __name__, url_prefix="/api/v1/pulumi")
@pulumi_bp.route("", methods=["GET"])
@require_token
def pulumi(): return jsonify({"ok": True})
