from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ovirt_bp = Blueprint("ovirt", __name__, url_prefix="/api/v1/ovirt")
@ovirt_bp.route("", methods=["GET"])
@require_token
def ovirt(): return jsonify({"ok": True})
