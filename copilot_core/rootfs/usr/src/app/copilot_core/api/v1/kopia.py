from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kopia_bp = Blueprint("kopia", __name__, url_prefix="/api/v1/kopia")
@kopia_bp.route("", methods=["GET"])
@require_token
def kopia(): return jsonify({"ok": True})
