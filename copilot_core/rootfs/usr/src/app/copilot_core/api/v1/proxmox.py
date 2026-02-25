from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
proxmox_bp = Blueprint("proxmox", __name__, url_prefix="/api/v1/proxmox")
@proxmox_bp.route("", methods=["GET"])
@require_token
def proxmox(): return jsonify({"ok": True})
