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

_LOGGER = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/v1/chat")


# =============================================================================
# Chat Session Management
# =============================================================================

@chat_bp.route("/sessions", methods=["POST"])
def create_chat_session():
    """Neue Chat-Session erstellen."""
    data = request.get_json() or {}
    
    session_id = f"chat_{uuid.uuid4().hex[:12]}"
    user_id = data.get("user_id", "default")
    character = data.get("character", "styx")  # styx, assistant, expert, etc.
    
    # TODO: Session in ConversationMemory speichern
    _LOGGER.info(f"Chat session created: {session_id} (user={user_id}, character={character})")
    
    return jsonify({
        "session_id": session_id,
        "user_id": user_id,
        "character": character,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


@chat_bp.route("/sessions/<session_id>", methods=["GET"])
def get_chat_session(session_id: str):
    """Chat-Session Details laden."""
    # TODO: Aus ConversationMemory laden
    return jsonify({
        "session_id": session_id,
        "status": "active",
        "message_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


@chat_bp.route("/sessions/<session_id>", methods=["DELETE"])
def delete_chat_session(session_id: str):
    """Chat-Session löschen."""
    # TODO: Session aus ConversationMemory löschen
    return jsonify({
        "success": True,
        "session_id": session_id,
    })


# =============================================================================
# Chat Messages
# =============================================================================

@chat_bp.route("/sessions/<session_id>/messages", methods=["POST"])
def send_message(session_id: str):
    """Nachricht an Chat senden — mit Kontext aus Neurons, Habitus, Zones."""
    data = request.get_json()
    
    if not data or "message" not in data:
        return jsonify({"error": "Message required"}), 400
    
    message = data["message"]
    context = data.get("context", {})  # Optional: Zone, Mood, etc.
    
    _LOGGER.info(f"Chat message in session {session_id}: {message[:100]}...")
    
    # ChatHandler verwenden (mit RAG + LLM)
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        
        handler = ChatHandler()
        
        # Kontext anreichern (Neurons, Habitus, Zones)
        enriched_context = _enrich_context(context)
        
        # Antwort generieren
        response = handler.chat(
            query=message,
            session_id=session_id,
            context=enriched_context,
        )
        
        return jsonify({
            "success": True,
            "message": message,
            "response": response.get("response", ""),
            "sources": response.get("sources", []),
            "context_used": enriched_context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
    except Exception as e:
        _LOGGER.error(f"Chat error: {e}")
        return jsonify({
            "error": str(e),
            "fallback": "Entschuldigung, ich habe ein Problem. Bitte versuche es später erneut.",
        }), 500


@chat_bp.route("/sessions/<session_id>/messages", methods=["GET"])
def get_messages(session_id: str):
    """Chat-History laden."""
    limit = request.args.get("limit", "50", type=int)
    
    # TODO: Aus ConversationMemory laden
    messages = [
        {
            "id": f"msg_{i}",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Beispiel-Nachricht {i}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for i in range(limit)
    ]
    
    return jsonify({
        "session_id": session_id,
        "total": len(messages),
        "messages": messages,
    })


# =============================================================================
# Voice Chat (STT + TTS)
# =============================================================================

@chat_bp.route("/sessions/<session_id>/voice", methods=["POST"])
def voice_message(session_id: str):
    """Voice-Nachricht senden (Whisper STT → Chat → TTS)."""
    if "audio" not in request.files:
        return jsonify({"error": "Audio file required"}), 400
    
    audio_file = request.files["audio"]
    audio_data = audio_file.read()
    
    _LOGGER.info(f"Voice message in session {session_id}: {len(audio_data)} bytes")
    
    # TODO: Whisper STT
    transcription = "Transkribierter Text"  # Stub
    
    # Chat-Antwort
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        handler = ChatHandler()
        response = handler.chat(query=transcription, session_id=session_id)
        
        # TODO: TTS
        audio_response = None  # Stub
        
        return jsonify({
            "success": True,
            "transcription": transcription,
            "response": response.get("response", ""),
            "audio_response": audio_response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
    except Exception as e:
        _LOGGER.error(f"Voice chat error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Characters / Personas
# =============================================================================

@chat_bp.route("/characters", methods=["GET"])
def get_characters():
    """Verfügbare Character-Personas."""
    characters = [
        {
            "id": "styx",
            "name": "Styx",
            "description": "Haupt-Assistent, freundlich, proaktiv",
            "voice": "de-DE-standard",
        },
        {
            "id": "expert",
            "name": "Expert",
            "description": "Technisch detailliert, präzise",
            "voice": "de-DE-neutral",
        },
        {
            "id": "coach",
            "name": "Coach",
            "description": "Motivierend, zielorientiert",
            "voice": "de-DE-warm",
        },
    ]
    
    return jsonify({
        "total": len(characters),
        "characters": characters,
    })


@chat_bp.route("/sessions/<session_id>/character", methods=["PUT"])
def set_character(session_id: str):
    """Character für Session setzen."""
    data = request.get_json()
    character_id = data.get("character_id", "styx")
    
    # TODO: In Session speichern
    return jsonify({
        "success": True,
        "session_id": session_id,
        "character_id": character_id,
    })


# =============================================================================
# Helpers
# =============================================================================

def _enrich_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Kontext mit Neurons, Habitus, Zones anreichern."""
    enriched = {**context}
    
    # Neurons hinzufügen (aktueller Zustand)
    try:
        from copilot_core.neurons.manager import NeuronManager
        manager = NeuronManager()
        result = manager.evaluate()
        enriched["neurons"] = {
            "context": result.context_values if hasattr(result, "context_values") else {},
            "state": result.state_values if hasattr(result, "state_values") else {},
            "mood": result.mood_values if hasattr(result, "mood_values") else {},
            "dominant_mood": result.dominant_mood if hasattr(result, "dominant_mood") else None,
        }
    except Exception as e:
        _LOGGER.warning(f"Could not enrich neurons: {e}")
    
    # Habitus hinzufügen (gelernte Patterns)
    try:
        from copilot_core.habitus.habitus_storage import get_habitus_storage
        storage = get_habitus_storage()
        stats = storage.get_stats()
        enriched["habitus"] = {
            "patterns_learned": stats.get("patterns_total", 0),
            "active_patterns": stats.get("patterns_by_state", {}).get("active", 0),
        }
    except Exception as e:
        _LOGGER.warning(f"Could not enrich habitus: {e}")
    
    # Zones hinzufügen (aktive Zonen)
    try:
        from copilot_core.hub.habitus_zones import HabitusZoneEngine
        engine = HabitusZoneEngine()
        overview = engine.get_overview()
        enriched["zones"] = {
            "total_zones": overview.total_zones if hasattr(overview, "total_zones") else 0,
            "active_zones": overview.active_zones if hasattr(overview, "active_zones") else 0,
        }
    except Exception as e:
        _LOGGER.warning(f"Could not enrich zones: {e}")
    
    return enriched


# =============================================================================
# External Webhooks (für Telegram, WhatsApp, etc.)
# =============================================================================

@chat_bp.route("/webhooks/telegram", methods=["POST"])
def telegram_webhook():
    """Telegram Webhook — für externe Telegram-Bot-Integration."""
    data = request.get_json()
    
    # TODO: Telegram-Message parsen
    chat_id = data.get("message", {}).get("chat", {}).get("id")
    text = data.get("message", {}).get("text", "")
    
    if not text:
        return jsonify({"status": "ignored"}), 200
    
    # Chat-Antwort generieren
    session_id = f"telegram_{chat_id}"
    
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        handler = ChatHandler()
        response = handler.chat(query=text, session_id=session_id)
        
        # TODO: Antwort zurück an Telegram senden
        return jsonify({
            "status": "processed",
            "response": response.get("response", ""),
        })
        
    except Exception as e:
        _LOGGER.error(f"Telegram webhook error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@chat_bp.route("/webhooks/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """WhatsApp Webhook — für externe WhatsApp-Bot-Integration."""
    data = request.get_json()
    
    # TODO: WhatsApp-Message parsen
    # Similar to Telegram webhook
    
    return jsonify({"status": "processed"}), 200


@chat_bp.route("/webhooks/rest", methods=["POST"])
def rest_webhook():
    """Generic REST Webhook — für beliebige externe Dienste."""
    data = request.get_json()
    
    query = data.get("query")
    session_id = data.get("session_id", "rest_default")
    context = data.get("context", {})
    
    if not query:
        return jsonify({"error": "Query required"}), 400
    
    try:
        from copilot_core.styx.chat_handler import ChatHandler
        handler = ChatHandler()
        enriched_context = _enrich_context(context)
        response = handler.chat(query=query, session_id=session_id, context=enriched_context)
        
        return jsonify({
            "success": True,
            "query": query,
            "response": response.get("response", ""),
            "sources": response.get("sources", []),
            "context_used": enriched_context,
        })
        
    except Exception as e:
        _LOGGER.error(f"REST webhook error: {e}")
        return jsonify({"error": str(e)}), 500
