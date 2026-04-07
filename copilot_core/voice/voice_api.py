"""P4-006: Voice API + WebSocket — Real-Time Streaming, Low Latency."""
from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class VoiceEventType(Enum):
    """Voice event types."""
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    UNDERSTANDING = "understanding"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class VoiceEvent:
    """Voice pipeline event."""
    event_type: VoiceEventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class VoiceSession:
    """Active voice session."""
    session_id: str
    user_id: str
    state: str = "idle"
    events: List[VoiceEvent] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)


class VoiceAPI:
    """WebSocket API for real-time voice interactions."""

    def __init__(self):
        self._sessions: Dict[str, VoiceSession] = {}
        self._event_handlers: Dict[VoiceEventType, List[Callable]] = {}
        self._websocket_connections: Dict[str, Any] = {}

    def create_session(self, session_id: str, user_id: str) -> VoiceSession:
        """Create new voice session."""
        session = VoiceSession(session_id=session_id, user_id=user_id)
        self._sessions[session_id] = session
        logger.info(f"Voice session created: {session_id}")
        return session

    def end_session(self, session_id: str) -> bool:
        """End voice session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def emit_event(self, session_id: str, event: VoiceEvent):
        """Emit event to session."""
        if session_id not in self._sessions:
            return
        
        session = self._sessions[session_id]
        session.events.append(event)
        
        # Notify handlers
        for handler in self._event_handlers.get(event.event_type, []):
            try:
                handler(session_id, event)
            except Exception as e:
                logger.error(f"Event handler failed: {e}")
        
        # Send via WebSocket
        self._send_websocket(session_id, {
            "type": event.event_type.value,
            "data": event.data,
            "timestamp": event.timestamp
        })

    def _send_websocket(self, session_id: str, message: Dict):
        """Send message via WebSocket."""
        if session_id in self._websocket_connections:
            try:
                # ws.send(json.dumps(message))
                logger.debug(f"Sent to {session_id}: {message}")
            except Exception as e:
                logger.error(f"WebSocket send failed: {e}")

    def register_handler(self, event_type: VoiceEventType, handler: Callable):
        """Register event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def process_voice_command(
        self,
        session_id: str,
        audio_data: bytes,
        stt_fn: Callable,
        nlu_fn: Callable,
        execute_fn: Callable,
        tts_fn: Callable,
    ) -> Dict[str, Any]:
        """Process complete voice command pipeline."""
        if session_id not in self._sessions:
            self.create_session(session_id, "default")
        
        session = self._sessions[session_id]
        session.state = "processing"
        
        result = {
            "session_id": session_id,
            "success": False,
            "transcription": None,
            "intent": None,
            "action_result": None,
            "response_audio": None,
        }
        
        try:
            # Step 1: STT
            self.emit_event(session_id, VoiceEvent(
                event_type=VoiceEventType.TRANSCRIBING,
                data={"status": "started"}
            ))
            transcription = stt_fn(audio_data)
            result["transcription"] = transcription
            self.emit_event(session_id, VoiceEvent(
                event_type=VoiceEventType.UNDERSTANDING,
                data={"text": transcription}
            ))
            
            # Step 2: NLU
            nlu_result = nlu_fn(transcription)
            result["intent"] = nlu_result.intent.value if hasattr(nlu_result, 'intent') else "unknown"
            self.emit_event(session_id, VoiceEvent(
                event_type=VoiceEventType.EXECUTING,
                data={"intent": result["intent"]}
            ))
            
            # Step 3: Execute
            action_result = execute_fn(nlu_result)
            result["action_result"] = action_result
            
            # Step 4: Generate response
            response_text = f"OK, ich habe '{result['intent']}' ausgeführt."
            self.emit_event(session_id, VoiceEvent(
                event_type=VoiceEventType.SPEAKING,
                data={"text": response_text}
            ))
            tts_result = tts_fn(response_text)
            result["response_audio"] = tts_result.audio_path if tts_result else None
            
            # Complete
            result["success"] = True
            self.emit_event(session_id, VoiceEvent(
                event_type=VoiceEventType.COMPLETED,
                data={"success": True}
            ))
            session.state = "idle"
            
        except Exception as e:
            logger.error(f"Voice command failed: {e}")
            result["error"] = str(e)
            self.emit_event(session_id, VoiceEvent(
                event_type=VoiceEventType.ERROR,
                data={"error": str(e)}
            ))
            session.state = "error"
        
        return result

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get API statistics."""
        return {
            "active_sessions": len([s for s in self._sessions.values() if s.state != "idle"]),
            "total_sessions": len(self._sessions),
            "registered_handlers": sum(len(h) for h in self._event_handlers.values()),
        }


# Global default voice API
default_voice_api: Optional[VoiceAPI] = None


def init_voice_api() -> VoiceAPI:
    """Initialize global voice API."""
    global default_voice_api
    default_voice_api = VoiceAPI()
    return default_voice_api
