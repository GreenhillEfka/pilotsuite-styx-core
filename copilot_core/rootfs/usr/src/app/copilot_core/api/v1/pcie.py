from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pcie_bp = Blueprint("pcie", __name__, url_prefix="/api/v1/pcie")
@pcie_bp.route("", methods=["GET"])
@require_token
def pcie(): return jsonify({"ok": True})
