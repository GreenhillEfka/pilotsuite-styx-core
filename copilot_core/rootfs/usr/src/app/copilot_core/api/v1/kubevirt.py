from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kubevirt_bp = Blueprint("kubevirt", __name__, url_prefix="/api/v1/kubevirt")
@kubevirt_bp.route("", methods=["GET"])
@require_token
def kubevirt(): return jsonify({"ok": True})
