from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
protonmail_bp = Blueprint("protonmail", __name__, url_prefix="/api/v1/protonmail")
@protonmail_bp.route("", methods=["GET"])
@require_token
def protonmail(): return jsonify({"ok": True})
