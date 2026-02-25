from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nginxingress_bp = Blueprint("nginxingress", __name__, url_prefix="/api/v1/nginxingress")
@nginxingress_bp.route("", methods=["GET"])
@require_token
def nginxingress(): return jsonify({"ok": True})
