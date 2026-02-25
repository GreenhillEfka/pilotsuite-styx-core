from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kubefed_bp = Blueprint("kubefed", __name__, url_prefix="/api/v1/kubefed")
@kubefed_bp.route("", methods=["GET"])
@require_token
def kubefed(): return jsonify({"ok": True})
