from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
directadmin_bp = Blueprint("directadmin", __name__, url_prefix="/api/v1/directadmin")
@directadmin_bp.route("", methods=["GET"])
@require_token
def directadmin(): return jsonify({"ok": True})
