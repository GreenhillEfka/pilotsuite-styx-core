from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fax_bp = Blueprint("fax", __name__, url_prefix="/api/v1/fax")
@fax_bp.route("", methods=["GET"])
@require_token
def fax(): return jsonify({"ok": True})
