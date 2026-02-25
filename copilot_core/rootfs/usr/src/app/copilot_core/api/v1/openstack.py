from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
openstack_bp = Blueprint("openstack", __name__, url_prefix="/api/v1/openstack")
@openstack_bp.route("", methods=["GET"])
@require_token
def openstack(): return jsonify({"ok": True})
