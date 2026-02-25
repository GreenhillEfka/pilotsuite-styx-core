from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ansible_bp = Blueprint("ansible", __name__, url_prefix="/api/v1/ansible")
@ansible_bp.route("", methods=["GET"])
@require_token
def ansible(): return jsonify({"ok": True})
