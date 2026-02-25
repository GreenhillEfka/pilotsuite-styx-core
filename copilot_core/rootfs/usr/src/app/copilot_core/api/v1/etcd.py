from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
etcd_bp = Blueprint("etcd", __name__, url_prefix="/api/v1/etcd")
@etcd_bp.route("", methods=["GET"])
@require_token
def etcd(): return jsonify({"ok": True})
