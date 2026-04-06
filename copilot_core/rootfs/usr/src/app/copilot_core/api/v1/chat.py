"""Chat API — Externer Zugang zum PilotSuite Chat-System.

Diese API macht das Chat-System für EXTERNE Dienste verfügbar:
- Telegram, WhatsApp, Web-Clients
- Drittanbieter-Integrationen
- GraphQL / REST / WebSocket

Features:
- Chat mit Kontext (Neurons, Habitus, Zones)
- Voice-Input (Whisper STT)
- Voice-Output (TTS)
- Character-Personas
- Conversation Memory
- RAG-Integration (lokales Wissen)
- SearXNG (externes Wissen)
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid

from copilot_core.api.api_errors import bad_request, internal_error

_LOGGER = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/v1/chat")


@chat_bp.route("/sessions", methods=["POST"])
def create_chat_session():
    """Neue Chat-Session erstellen."""
    data = request.get_json() or {}
    session_id = f"chat_{uuid.uuid4().hex[:12]}"
    user_id = data.get("user_id", "default")
    character = data.get("character", "styx")
    
    _LOGGER.info(f"Chat session created: {session_id} (user={user_id})")
    
    return jsonify({
        "session_id": session_id,
        "user_id": user_id,
        "character": character,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


@chat_bp.route("/sessions/<session_id>/messages", methods=["POST"])
def send_message(session_id: str):
    """Nachricht an Chat senden — mit Kontext aus Neurons, Habitus, Zones."""
    data = request.get_json()
    
    if not data or "message" not in data:
        return bad_request("Message required", req=request)
    
    message = data["message"]
    context = data.get("context", {})
    
    _LOGGER.info(f"Chat message in session {session_id}: {message[:50]}...")
    
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        handler = ChatHandler()
        response = handler.chat(query=message, session_id=session_id, context=context)
        
        return jsonify({
            "success": True,
            "message": message,
            "response": response.get("response", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        _LOGGER.error(f"Chat error: {e}")
        return internal_error("Chat processing failed", str(e), request)


@chat_bp.route("/webhooks/telegram", methods=["POST"])
def telegram_webhook():
    """Telegram Webhook."""
    data = request.get_json()
    chat_id = data.get("message", {}).get("chat", {}).get("id")
    text = data.get("message", {}).get("text", "")
    
    if not text:
        return jsonify({"status": "ignored"}), 200
    
    session_id = f"telegram_{chat_id}"
    
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        handler = ChatHandler()
        response = handler.chat(query=text, session_id=session_id)
        
        return jsonify({"status": "processed", "response": response.get("response", "")})
    except Exception as e:
        return internal_error("Chat processing failed", str(e), request)


@chat_bp.route("/webhooks/rest", methods=["POST"])
def rest_webhook():
    """Generic REST Webhook."""
    data = request.get_json()
    query = data.get("query")
    session_id = data.get("session_id", "rest_default")
    
    if not query:
        return bad_request("Query required", req=request)
    
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        handler = ChatHandler()
        response = handler.chat(query=query, session_id=session_id)
        
        return jsonify({
            "success": True,
            "query": query,
            "response": response.get("response", ""),
        })
    except Exception as e:
        return internal_error("Chat processing failed", str(e), request)
