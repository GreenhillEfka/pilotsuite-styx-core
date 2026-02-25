from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
grub_bp = Blueprint("grub", __name__, url_prefix="/api/v1/grub")
@grub_bp.route("", methods=["GET"])
@require_token
def grub(): return jsonify({"ok": True})
