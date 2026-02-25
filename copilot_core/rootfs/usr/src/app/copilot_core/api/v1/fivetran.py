from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fivetran_bp = Blueprint("fivetran", __name__, url_prefix="/api/v1/fivetran")
@fivetran_bp.route("", methods=["GET"])
@require_token
def fivetran(): return jsonify({"ok": True})
