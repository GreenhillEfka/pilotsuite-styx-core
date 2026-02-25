from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ceph_bp = Blueprint("ceph", __name__, url_prefix="/api/v1/ceph")
@ceph_bp.route("", methods=["GET"])
@require_token
def ceph(): return jsonify({"ok": True})
