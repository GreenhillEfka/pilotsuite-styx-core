from flask import Blueprint, jsonify
from copilot_core.api.security import requirep = Blueprint("_token
nats_bnats", __name__, url_prefix="/api/v1/nats")
@nats_bp.route("", methods=["GET"])
@require_token
def nats(): return jsonify({"ok": True})
