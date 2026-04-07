"""P4-003: Dialogue Management — Context Tracking, Multi-Turn."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DialogueState(Enum):
    """Dialogue states."""
    INIT = "init"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    WAITING_FOR_CLARIFICATION = "waiting_clarification"
    COMPLETED = "completed"


@dataclass
class DialogueTurn:
    """Single turn in dialogue."""
    turn_id: int
    user_utterance: str
    bot_response: Optional[str]
    intent: str
    entities: List[Dict]
    timestamp: float = field(default_factory=time.time)


@dataclass
class DialogueContext:
    """Context for dialogue session."""
    session_id: str
    user_id: str
    state: DialogueState
    turns: List[DialogueTurn] = field(default_factory=list)
    slots: Dict[str, Any] = field(default_factory=dict)
    last_intent: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class DialogueManager:
    """Manages multi-turn conversations."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._sessions: Dict[str, DialogueContext] = {}
        self._clarification_handlers: Dict[str, callable] = {}

    def create_session(self, session_id: str, user_id: str) -> DialogueContext:
        """Create new dialogue session."""
        context = DialogueContext(
            session_id=session_id,
            user_id=user_id,
            state=DialogueState.INIT
        )
        self._sessions[session_id] = context
        logger.info(f"Created dialogue session: {session_id}")
        return context

    def process_turn(
        self,
        session_id: str,
        user_utterance: str,
        nlu_result: Any,
    ) -> str:
        """Process a dialogue turn."""
        if session_id not in self._sessions:
            self.create_session(session_id, "default")
        
        context = self._sessions[session_id]
        context.state = DialogueState.PROCESSING
        
        # Get intent and entities
        intent = nlu_result.intent.value if hasattr(nlu_result, 'intent') else "unknown"
        entities = nlu_result.entities if hasattr(nlu_result, 'entities') else []
        
        # Update slots
        if hasattr(nlu_result, 'slots'):
            context.slots.update(nlu_result.slots)
        
        # Check if we need clarification
        if self._needs_clarification(context, intent):
            context.state = DialogueState.WAITING_FOR_CLARIFICATION
            response = self._ask_clarification(intent, context.slots)
        else:
            # Generate response
            response = self._generate_response(intent, context.slots)
            context.state = DialogueState.COMPLETED
        
        # Record turn
        turn = DialogueTurn(
            turn_id=len(context.turns) + 1,
            user_utterance=user_utterance,
            bot_response=response,
            intent=intent,
            entities=[{"name": e.name, "type": e.type, "value": e.value} for e in entities]
        )
        context.turns.append(turn)
        context.last_intent = intent
        context.updated_at = time.time()
        
        # Check max turns
        if len(context.turns) >= self.max_turns:
            context.state = DialogueState.COMPLETED
        
        return response

    def _needs_clarification(self, context: DialogueContext, intent: str) -> bool:
        """Check if clarification is needed."""
        # Check for missing required slots
        required_slots = {
            "turn_on": ["entity_type"],
            "turn_off": ["entity_type"],
            "set_value": ["entity_type", "value"],
        }
        
        required = required_slots.get(intent, [])
        for slot in required:
            if slot not in context.slots:
                return True
        
        return False

    def _ask_clarification(self, intent: str, slots: Dict) -> str:
        """Ask for clarification."""
        if "entity_type" not in slots:
            return "Welches Gerät möchtest du steuern?"
        if "value" not in slots:
            return "Auf welchen Wert soll ich einstellen?"
        return "Bitte bestätige deine Eingabe."

    def _generate_response(self, intent: str, slots: Dict) -> str:
        """Generate response based on intent and slots."""
        responses = {
            "turn_on": f"OK, ich schalte {slots.get('entity_name', 'das Gerät')} ein.",
            "turn_off": f"OK, ich schalte {slots.get('entity_name', 'das Gerät')} aus.",
            "set_value": f"OK, ich stelle {slots.get('entity_name', 'es')} auf {slots.get('value', 'den Wert')}.",
            "query_status": f"Der Status ist: aktiv.",
            "unknown": "Ich habe dich nicht verstanden. Bitte wiederhole.",
        }
        return responses.get(intent, responses["unknown"])

    def get_context(self, session_id: str) -> Optional[DialogueContext]:
        """Get dialogue context."""
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> bool:
        """End dialogue session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def get_history(self, session_id: str, limit: int = 10) -> List[DialogueTurn]:
        """Get dialogue history."""
        context = self._sessions.get(session_id)
        if context:
            return context.turns[-limit:]
        return []


# Global default dialogue manager
default_dialogue: Optional[DialogueManager] = None


def init_dialogue_manager(max_turns: int = 10) -> DialogueManager:
    """Initialize global dialogue manager."""
    global default_dialogue
    default_dialogue = DialogueManager(max_turns)
    return default_dialogue


def process_dialogue_turn(session_id: str, utterance: str, nlu: Any) -> str:
    """Convenience function for dialogue turn."""
    if default_dialogue:
        return default_dialogue.process_turn(session_id, utterance, nlu)
    return "Dialog system not initialized"
