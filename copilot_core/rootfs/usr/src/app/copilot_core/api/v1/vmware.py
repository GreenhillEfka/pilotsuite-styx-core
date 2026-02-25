from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vmware_bp = Blueprint("vmware", __name__, url_prefix="/api/v1/vmware")
@vmware_bp.route("", methods=["GET"])
@require_token
def vmware(): return jsonify({"ok": True})
