from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sata_bp = Blueprint("sata", __name__, url_prefix="/api/v1/sata")
@sata_bp.route("", methods=["GET"])
@require_token
def sata(): return jsonify({"ok": True})
