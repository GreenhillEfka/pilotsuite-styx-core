from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pydio_bp = Blueprint("pydio", __name__, url_prefix="/api/v1/pydio")
@pydio_bp.route("", methods=["GET"])
@require_token
def pydio(): return jsonify({"ok": True})
