from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ovn_bp = Blueprint("ovn", __name__, url_prefix="/api/v1/ovn")
@ovn_bp.route("", methods=["GET"])
@require_token
def ovn(): return jsonify({"ok": True})
