from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dospaces_bp = Blueprint("dospaces", __name__, url_prefix="/api/v1/dospaces")
@dospaces_bp.route("", methods=["GET"])
@require_token
def dospaces(): return jsonify({"ok": True})
