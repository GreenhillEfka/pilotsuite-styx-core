from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
onnxruntime_bp = Blueprint("onnxruntime", __name__, url_prefix="/api/v1/onnxruntime")
@onnxruntime_bp.route("", methods=["GET"])
@require_token
def onnxruntime(): return jsonify({"ok": True})
