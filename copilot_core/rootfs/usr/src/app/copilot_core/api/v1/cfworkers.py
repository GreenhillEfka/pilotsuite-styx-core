from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cfworkers_bp = Blueprint("cfworkers", __name__, url_prefix="/api/v1/cfworkers")
@cfworkers_bp.route("", methods=["GET"])
@require_token
def cfworkers(): return jsonify({"ok": True})
