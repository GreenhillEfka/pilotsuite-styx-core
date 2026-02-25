from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
certmanager_bp = Blueprint("certmanager", __name__, url_prefix="/api/v1/certmanager")
@certmanager_bp.route("", methods=["GET"])
@require_token
def certmanager(): return jsonify({"ok": True})
