"""
Dialog State Machine — Multi-Turn Voice Dialog Management (Slice 74)

Implements FSM + Context Stack for multi-turn voice dialogs with:
- Finite State Machine for well-defined flows (climate, lights, scenes)
- Context Stack for nested interruptions
- 30-second timeout with graceful decay
- Persistence in /data/dialog_state.json (survives restarts)

Owner: homeclaw
Priority: P1 (blocks multi-turn UX)
Effort: ~4h
Status: IMPLEMENTED (2026-04-08)
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class DialogState:
    """Structured dialog state (not full transcript!)."""
    state: str  # IDLE, ACTIVE, CONFIRMING, CLARIFYING, INTERRUPTED
    active_intent: Optional[str]
    slot_values: Dict[str, Any]
    context_stack: List[Dict[str, Any]]
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DialogStateMachine:
    """FSM + Context Stack for multi-turn voice dialogs.
    
    States:
    - IDLE: Awaiting command
    - ACTIVE: Executing intent
    - CONFIRMING: Awaiting user confirmation
    - CLARIFYING: Asking clarification question
    - INTERRUPTED: Nested context active
    
    Confirmed UX: spoken + dashboard (Beides)
    Persistence: survives restarts via /data/dialog_state.json
    Language: German only (DE), English later
    """
    
    STATES = {
        'IDLE': 'awaiting_command',
        'ACTIVE': 'executing_intent',
        'CONFIRMING': 'awaiting_user_confirmation',
        'CLARIFYING': 'asking_clarification_question',
        'INTERRUPTED': 'nested_context_active',
    }
    
    TIMEOUT_SECONDS = 30  # Context expires after 30s of silence
    
    def __init__(self, data_dir: str = '/data'):
        self.data_dir = data_dir
        self.persistence_path = os.path.join(data_dir, 'dialog_state.json')
        self.state = DialogState(
            state='IDLE',
            active_intent=None,
            slot_values={},
            context_stack=[],
            last_activity_ts=None,
            session_id=None,
            user_id=None,
        )
        self._load()  # Load persisted state on init
    
    # ─────────────────────────────────────────────────────────────────────────
    # STATE TRANSITIONS
    # ─────────────────────────────────────────────────────────────────────────
    
    def activate_intent(
        self,
        intent: str,
        slots: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> DialogState:
        """Activate new intent. Push current to stack if active (interruption)."""
        slots = slots or {}
        
        # Push current to stack if active (interruption handling)
        if self.state.state == 'ACTIVE' and self.state.active_intent:
            self.state.context_stack.append({
                'intent': self.state.active_intent,
                'slots': dict(self.state.slot_values),
                'state': self.state.state,
            })
            self.state.state = 'INTERRUPTED'

        # Activate new intent after preserving any interrupted context.
        self.state.active_intent = intent
        self.state.slot_values = dict(slots)
        self.state.state = 'ACTIVE'
        self.state.last_activity_ts = time.time()
        self.state.session_id = session_id
        self.state.user_id = user_id

        self._persist()
        return self.state
    
    def set_confirming(
        self,
        missing_slots: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DialogState:
        """Transition to CONFIRMING state (awaiting user confirmation)."""
        if missing_slots:
            self.state.slot_values['_missing'] = list(missing_slots)
        if metadata:
            self.state.slot_values.update(dict(metadata))

        self.state.state = 'CONFIRMING'
        self.state.last_activity_ts = time.time()
        self._persist()
        return self.state

    def set_clarifying(
        self,
        clarification_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DialogState:
        """Transition to CLARIFYING state (asking clarification question)."""
        self.state.slot_values['_clarification'] = clarification_text
        if metadata:
            self.state.slot_values.update(dict(metadata))
        self.state.state = 'CLARIFYING'
        self.state.last_activity_ts = time.time()
        self._persist()
        return self.state
    
    def confirm_action(self) -> DialogState:
        """User confirmed pending action. Execute and pop context stack."""
        # Pop from context stack if available (return from interruption)
        if self.state.context_stack:
            popped = self.state.context_stack.pop()
            self.state.active_intent = popped['intent']
            self.state.slot_values = popped['slots']
            self.state.state = popped['state']
        else:
            # No context → back to IDLE
            self.state.active_intent = None
            self.state.slot_values = {}
            self.state.state = 'IDLE'
        
        self.state.last_activity_ts = time.time()
        self._persist()
        return self.state
    
    def cancel_action(self) -> DialogState:
        """User cancelled. Pop context stack or go IDLE."""
        if self.state.context_stack:
            popped = self.state.context_stack.pop()
            self.state.active_intent = popped['intent']
            self.state.slot_values = popped['slots']
            self.state.state = popped['state']
        else:
            self.state.active_intent = None
            self.state.slot_values = {}
            self.state.state = 'IDLE'
        
        self.state.last_activity_ts = time.time()
        self._persist()
        return self.state
    
    # ─────────────────────────────────────────────────────────────────────────
    # TIMEOUT & DECAY
    # ─────────────────────────────────────────────────────────────────────────
    
    def check_timeout(self) -> bool:
        """Check if dialog timed out (30s decay)."""
        if not self.state.last_activity_ts:
            return True
        
        elapsed = time.time() - self.state.last_activity_ts
        return elapsed > self.TIMEOUT_SECONDS
    
    def decay(self) -> DialogState:
        """Handle timeout decay. Reset to IDLE if timed out."""
        if self.check_timeout():
            self.state.state = 'IDLE'
            self.state.active_intent = None
            self.state.slot_values = {}
            self.state.context_stack = []
            self.state.last_activity_ts = None
            self._persist()
        
        return self.state
    
    # ─────────────────────────────────────────────────────────────────────────
    # CONFIRMATION QUESTIONS (German, spoken + dashboard)
    # ─────────────────────────────────────────────────────────────────────────
    
    def generate_confirmation_question(self) -> Optional[str]:
        """Generate German confirmation question (spoken + dashboard).
        
        Returns:
            Confirmation question string or None if not in CONFIRMING state
        """
        if self.state.state != 'CONFIRMING':
            return None

        explicit_prompt = self.state.slot_values.get('_confirmation_prompt')
        if isinstance(explicit_prompt, str) and explicit_prompt.strip():
            return explicit_prompt
        
        intent_desc = self._describe_intent(self.state.active_intent)
        slots_desc = self._describe_slots(self.state.slot_values)
        
        return f"{intent_desc} {slots_desc}? Bitte bestätigen."
    
    def generate_clarification_question(self) -> Optional[str]:
        """Generate German clarification question.
        
        Returns:
            Clarification question string or None if not in CLARIFYING state
        """
        if self.state.state != 'CLARIFYING':
            return None
        
        return self.state.slot_values.get('_clarification', 
                                          "Kannst du das bitte genauer beschreiben?")
    
    def _describe_intent(self, intent: Optional[str]) -> str:
        """Convert intent ID to German description."""
        if not intent:
            return "Aktion"
        
        intent_map = {
            'climate.set_temperature': 'Temperatur setzen',
            'climate.set_hvac_mode': 'Modus setzen',
            'light.turn_on': 'Licht einschalten',
            'light.turn_off': 'Licht ausschalten',
            'light.set_brightness': 'Helligkeit setzen',
            'scene.activate': 'Szene aktivieren',
            'cover.open_cover': 'Rollladen öffnen',
            'cover.close_cover': 'Rollladen schließen',
        }
        
        return intent_map.get(intent, intent)
    
    def _describe_slots(self, slots: Dict[str, Any]) -> str:
        """Convert slot values to German description."""
        if not slots:
            return ""
        
        parts = []
        
        if 'room' in slots:
            parts.append(f"im {slots['room']}")
        
        if 'target_temp' in slots:
            parts.append(f"auf {slots['target_temp']} Grad")
        
        if 'hvac_mode' in slots:
            mode_map = {
                'heat': 'Heizen',
                'cool': 'Kühlen',
                'auto': 'Auto',
                'off': 'Aus',
            }
            parts.append(f"auf {mode_map.get(slots['hvac_mode'], slots['hvac_mode'])}")
        
        if 'brightness' in slots:
            parts.append(f"auf {slots['brightness']}%")
        
        return " ".join(parts)
    
    # ─────────────────────────────────────────────────────────────────────────
    # PERSISTENCE (survives HA restarts)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _persist(self):
        """Save state to /data/dialog_state.json."""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            
            data = asdict(self.state)
            with open(self.persistence_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            _LOGGER.warning("Failed to persist dialog state: %s", e)
    
    def _load(self) -> bool:
        """Load state from persistence (after restart)."""
        if not os.path.exists(self.persistence_path):
            return False
        
        try:
            with open(self.persistence_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.state = DialogState(**data)
            
            # Check for timeout on loaded state
            if self.check_timeout():
                self.decay()
            
            return True
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            _LOGGER.warning("Corrupted dialog state file, resetting: %s", e)
            self.state = DialogState(
                state='IDLE',
                active_intent=None,
                slot_values={},
                context_stack=[],
                last_activity_ts=None,
                session_id=None,
                user_id=None,
            )
            return False
    
    def get_state(self) -> DialogState:
        """Get current dialog state."""
        return self.state

    def merge_metadata(self, metadata: Optional[Dict[str, Any]] = None) -> DialogState:
        """Merge lightweight metadata into the current state and persist it."""
        if metadata:
            self.state.slot_values.update(dict(metadata))
            self._persist()
        return self.state

    def reset(
        self,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> DialogState:
        """Reset to IDLE state, optionally preserving lightweight metadata."""
        self.state = DialogState(
            state='IDLE',
            active_intent=None,
            slot_values=dict(metadata or {}),
            context_stack=[],
            last_activity_ts=time.time(),
            session_id=session_id,
            user_id=user_id,
        )
        self._persist()
        return self.state


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL INSTANCE (for API access)
# ─────────────────────────────────────────────────────────────────────────────

_dialog_machine: Optional[DialogStateMachine] = None


def get_dialog_machine(data_dir: str = '/data') -> DialogStateMachine:
    """Get or create global dialog machine instance."""
    global _dialog_machine
    if _dialog_machine is None:
        _dialog_machine = DialogStateMachine(data_dir=data_dir)
    return _dialog_machine
