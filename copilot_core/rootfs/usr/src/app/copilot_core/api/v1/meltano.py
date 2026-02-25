from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
meltano_bp = Blueprint("meltano", __name__, url_prefix="/api/v1/meltano")
@meltano_bp.route("", methods=["GET"])
@require_token
def meltano(): return jsonify({"ok": True})
