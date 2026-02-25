from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vsphere_bp = Blueprint("vsphere", __name__, url_prefix="/api/v1/vsphere")
@vsphere_bp.route("", methods=["GET"])
@require_token
def vsphere(): return jsonify({"ok": True})
