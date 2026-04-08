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
Status: IMPLEMENTING (started 2026-04-08 14:00)
"""

import json
import os
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class DialogState:
    """Structured dialog state (not full transcript!)"""
    state: str  # IDLE, ACTIVE, CONFIRMING, CLARIFYING, INTERRUPTED
    active_intent: Optional[str]
    slot_values: Dict[str, Any]
    context_stack: List[Dict[str, Any]]
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]


class DialogStateMachine:
    """
    FSM + Context Stack for multi-turn voice dialogs.
    
    States:
    - IDLE: Awaiting command
    - ACTIVE: Executing intent
    - CONFIRMING: Awaiting user confirmation
    - CLARIFYING: Asking clarification question
    - INTERRUPTED: Nested context active
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
    
    def activate_intent(self, intent: str, slots: Dict[str, Any], 
                        session_id: Optional[str] = None,
                        user_id: Optional[str] = None) -> DialogState:
        """
        Activate new intent. Push current to stack if active (interruption).
        
        Args:
            intent: Intent identifier (e.g., 'climate.set_temperature')
            slots: Slot values (e.g., {'room': 'kitchen', 'target_temp': 22})
            session_id: Voice session identifier
            user_id: User identifier for personalization
        
        Returns:
            Updated DialogState
        """
        # Push current to stack if active (interruption handling)
        if self.state.state == 'ACTIVE' and self.state.active_intent:
            self.state.context_stack.append({
                'intent': self.state.active_intent,
                'slots': self.state.slot_values,
                'state': self.state.state,
            })
            self.state.state = 'INTERRUPTED'
        
        # Activate new intent
        self.state.active_intent = intent
        self.state.slot_values = slots
        self.state.state = 'ACTIVE'
        self.state.last_activity_ts = time.time()
        self.state.session_id = session_id
        self.state.user_id = user_id
        
        self._persist()
        return self.state
    
    def set_confirming(self, missing_slots: Optional[List[str]] = None) -> DialogState:
        """
        Transition to CONFIRMING state (awaiting user confirmation).
        
        Args:
            missing_slots: List of missing slot names (if any)
        
        Returns:
            Updated DialogState
        """
        if missing_slots:
            self.state.slot_values['_missing'] = missing_slots
        
        self.state.state = 'CONFIRMING'
        self.state.last_activity_ts = time.time()
        self._persist()
        return self.state
    
    def set_clarifying(self, clarification_text: str) -> DialogState:
        """
        Transition to CLARIFYING state (asking clarification question).
        
        Args:
            clarification_text: The clarification question to ask
        
        Returns:
            Updated DialogState
        """
        self.state.slot_values['_clarification'] = clarification_text
        self.state.state = 'CLARIFYING'
        self.state.last_activity_ts = time.time()
        self._persist()
        return self.state
    
    def confirm_action(self) -> DialogState:
        """
        User confirmed pending action. Execute and pop context stack.
        
        Returns:
            Updated DialogState (IDLE or restored from stack)
        """
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
        """
        User cancelled. Pop context stack or go IDLE.
        
        Returns:
            Updated DialogState
        """
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
        """
        Check if dialog timed out (30s decay).
        
        Returns:
            True if timed out, False otherwise
        """
        if not self.state.last_activity_ts:
            return True
        
        elapsed = time.time() - self.state.last_activity_ts
        return elapsed > self.TIMEOUT_SECONDS
    
    def decay(self) -> DialogState:
        """
        Handle timeout decay. Reset to IDLE if timed out.
        
        Returns:
            Updated DialogState
        """
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
        """
        Generate German confirmation question (spoken + dashboard).
        
        Returns:
            Confirmation question string or None if not in CONFIRMING state
        """
        if self.state.state != 'CONFIRMING':
            return None
        
        intent_desc = self._describe_intent(self.state.active_intent)
        slots_desc = self._describe_slots(self.state.slot_values)
        
        return f"{intent_desc} {slots_desc}? Bitte bestätigen."
    
    def generate_clarification_question(self) -> Optional[str]:
        """
        Generate German clarification question.
        
        Returns:
            Clarification question string or None if not in CLARIFYING state
        """
        if self.state.state != 'CLARIFYING':
            return None
        
        return self.state.slot_values.get('_clarification', 
                                          "Bitte genauer beschreiben.")
    
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
        """Save state to /data/dialog_state.json"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        data = asdict(self.state)
        with open(self.persistence_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load(self) -> bool:
        """Load state from persistence (after restart)"""
        if not os.path.exists(self.persistence_path):
            return False
        
        try:
            with open(self.persistence_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.state = DialogState(**data)
            return True
        except (json.JSONDecodeError, TypeError, KeyError):
            # Corrupted file → reset to IDLE
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
    
    def reset(self) -> DialogState:
        """Reset to IDLE state."""
        self.state = DialogState(
            state='IDLE',
            active_intent=None,
            slot_values={},
            context_stack=[],
            last_activity_ts=None,
            session_id=None,
            user_id=None,
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
