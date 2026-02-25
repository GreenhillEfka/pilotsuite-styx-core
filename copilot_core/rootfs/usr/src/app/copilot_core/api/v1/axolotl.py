from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
axolotl_bp = Blueprint("axolotl", __name__, url_prefix="/api/v1/axolotl")
@axolotl_bp.route("", methods=["GET"])
@require_token
def axolotl(): return jsonify({"ok": True})
