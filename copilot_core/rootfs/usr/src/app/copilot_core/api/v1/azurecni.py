from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
azurecni_bp = Blueprint("azurecni", __name__, url_prefix="/api/v1/azurecni")
@azurecni_bp.route("", methods=["GET"])
@require_token
def azurecni(): return jsonify({"ok": True})
