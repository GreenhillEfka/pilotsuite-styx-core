from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hoppscotch_bp = Blueprint("hoppscotch", __name__, url_prefix="/api/v1/hoppscotch")
@hoppscotch_bp.route("", methods=["GET"])
@require_token
def hoppscotch(): return jsonify({"ok": True})
