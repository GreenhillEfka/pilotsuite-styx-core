from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
opennebula_bp = Blueprint("opennebula", __name__, url_prefix="/api/v1/opennebula")
@opennebula_bp.route("", methods=["GET"])
@require_token
def opennebula(): return jsonify({"ok": True})
