from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
haproxy_bp = Blueprint("haproxy", __name__, url_prefix="/api/v1/haproxy")
@haproxy_bp.route("", methods=["GET"])
@require_token
def haproxy(): return jsonify({"ok": True})
