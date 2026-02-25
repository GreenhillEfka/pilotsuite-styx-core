from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tpm_bp = Blueprint("tpm", __name__, url_prefix="/api/v1/tpm")
@tpm_bp.route("", methods=["GET"])
@require_token
def tpm(): return jsonify({"ok": True})
