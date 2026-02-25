from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
binarysensor_bp = Blueprint("binarysensor", __name__, url_prefix="/api/v1/binarysensor")
@binarysensor_bp.route("", methods=["GET"])
@require_token
def binarysensor(): return jsonify({"ok": True})
