from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
portworx_bp = Blueprint("portworx", __name__, url_prefix="/api/v1/portworx")
@portworx_bp.route("", methods=["GET"])
@require_token
def portworx(): return jsonify({"ok": True})
