from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sas_bp = Blueprint("sas", __name__, url_prefix="/api/v1/sas")
@sas_bp.route("", methods=["GET"])
@require_token
def sas(): return jsonify({"ok": True})
