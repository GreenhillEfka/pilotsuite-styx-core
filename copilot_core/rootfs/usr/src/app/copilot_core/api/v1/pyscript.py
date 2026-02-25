from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pyscript_bp = Blueprint("pyscript", __name__, url_prefix="/api/v1/pyscript")
@pyscript_bp.route("", methods=["GET"])
@require_token
def pyscript(): return jsonify({"ok": True})
