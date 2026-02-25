from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pulsar_bp = Blueprint("pulsar", __name__, url_prefix="/api/v1/pulsar")
@pulsar_bp.route("", methods=["GET"])
@require_token
def pulsar(): return jsonify({"ok": True})
