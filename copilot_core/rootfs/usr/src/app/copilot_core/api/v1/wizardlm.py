from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wizardlm_bp = Blueprint("wizardlm", __name__, url_prefix="/api/v1/wizardlm")
@wizardlm_bp.route("", methods=["GET"])
@require_token
def wizardlm(): return jsonify({"ok": True})
