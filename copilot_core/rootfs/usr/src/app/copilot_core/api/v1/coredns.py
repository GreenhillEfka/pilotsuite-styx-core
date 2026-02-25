from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
coredns_bp = Blueprint("coredns", __name__, url_prefix="/api/v1/coredns")
@coredns_bp.route("", methods=["GET"])
@require_token
def coredns(): return jsonify({"ok": True})
