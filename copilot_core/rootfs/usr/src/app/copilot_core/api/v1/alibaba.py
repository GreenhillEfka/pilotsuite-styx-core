from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
alibaba_bp = Blueprint("alibaba", __name__, url_prefix="/api/v1/alibaba")
@alibaba_bp.route("", methods=["GET"])
@require_token
def alibaba(): return jsonify({"ok": True})
