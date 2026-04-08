"""Telegram Bot API endpoints for PilotSuite."""

from flask import Blueprint, request, jsonify
from copilot_core.api.security import require_token

telegram_bp = Blueprint('telegram', __name__, url_prefix='/telegram')

_bot = None


def init_telegram_api(bot):
    """Set the global bot instance for API access."""
    global _bot
    _bot = bot


@telegram_bp.route('/status', methods=['GET'])
@require_token
def telegram_status():
    """Return Telegram bot status."""
    if _bot:
        return jsonify({"enabled": True, "running": _bot.running})
    return jsonify({"enabled": False, "running": False})


@telegram_bp.route('/send', methods=['POST'])
@require_token
def telegram_send():
    """Send a proactive message to a Telegram chat."""
    data = request.get_json() or {}
    chat_id = data.get("chat_id")
    text = data.get("text")
    if not chat_id or not text:
        return jsonify({"error": "chat_id and text required"}), 400
    if not _bot or not _bot.running:
        return jsonify({"error": "Telegram bot not running"}), 503
    _bot.send_message(int(chat_id), text)
    return jsonify({"ok": True})
