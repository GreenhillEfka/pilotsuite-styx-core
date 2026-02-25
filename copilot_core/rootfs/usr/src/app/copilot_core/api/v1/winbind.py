from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
winbind_bp = Blueprint("winbind", __name__, url_prefix="/api/v1/winbind")
@winbind_bp.route("", methods=["GET"])
@require_token
def winbind(): return jsonify({"ok": True})
