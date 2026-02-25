from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
keycdn_bp = Blueprint("keycdn", __name__, url_prefix="/api/v1/keycdn")
@keycdn_bp.route("", methods=["GET"])
@require_token
def keycdn(): return jsonify({"ok": True})
