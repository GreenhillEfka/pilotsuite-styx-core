from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
snmp_bp = Blueprint("snmp", __name__, url_prefix="/api/v1/snmp")
@snmp_bp.route("", methods=["GET"])
@require_token
def snmp(): return jsonify({"ok": True})
