from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nvme_bp = Blueprint("nvme", __name__, url_prefix="/api/v1/nvme")
@nvme_bp.route("", methods=["GET"])
@require_token
def nvme(): return jsonify({"ok": True})
