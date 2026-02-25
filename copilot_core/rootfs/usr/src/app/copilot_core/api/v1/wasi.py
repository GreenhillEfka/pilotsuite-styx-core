from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wasi_bp = Blueprint("wasi", __name__, url_prefix="/api/v1/wasi")
@wasi_bp.route("", methods=["GET"])
@require_token
def wasi(): return jsonify({"ok": True})
