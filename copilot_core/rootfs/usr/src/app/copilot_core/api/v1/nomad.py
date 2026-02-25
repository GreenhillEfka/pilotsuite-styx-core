from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nomad_bp = Blueprint("nomad", __name__, url_prefix="/api/v1/nomad")
@nomad_bp.route("", methods=["GET"])
@require_token
def nomad(): return jsonify({"ok": True})
