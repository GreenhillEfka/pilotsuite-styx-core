from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pulumi_esc_bp = Blueprint("pulumi_esc", __name__, url_prefix="/api/v1/pulumi_esc")
@pulumi_esc_bp.route("", methods=["GET"])
@require_token
def pulumi_esc(): return jsonify({"ok": True})
