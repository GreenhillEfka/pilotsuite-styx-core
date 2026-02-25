from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kvm_bp = Blueprint("kvm", __name__, url_prefix="/api/v1/kvm")
@kvm_bp.route("", methods=["GET"])
@require_token
def kvm(): return jsonify({"ok": True})
