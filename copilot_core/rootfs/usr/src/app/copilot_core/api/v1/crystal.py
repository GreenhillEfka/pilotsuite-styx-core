from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
crystal_bp = Blueprint("crystal", __name__, url_prefix="/api/v1/crystal")
@crystal_bp.route("", methods=["GET"])
@require_token
def crystal(): return jsonify({"ok": True})
