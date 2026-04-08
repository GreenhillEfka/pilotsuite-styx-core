"""
Voice API Endpoints — Dialog State Management (Slice 74)

Endpoints:
- POST /api/v1/voice/dialog/state — Get current dialog state
- POST /api/v1/voice/dialog/activate — Activate new intent
- POST /api/v1/voice/dialog/confirm — User confirms pending action
- POST /api/v1/voice/dialog/cancel — User cancels pending action
- POST /api/v1/voice/dialog/clarify — Get clarification question
- POST /api/v1/voice/dialog/timeout — Check/handle timeout

Owner: homeclaw
Priority: P1
Effort: ~1h (part of Task 1)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from copilot_core.voice.dialog_state import (
    get_dialog_machine, 
    DialogStateMachine,
    DialogState,
)


router = APIRouter(prefix="/voice", tags=["voice"])


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ─────────────────────────────────────────────────────────────────────────────

class ActivateIntentRequest(BaseModel):
    intent: str = Field(..., description="Intent identifier")
    slots: Dict[str, Any] = Field(default_factory=dict, description="Slot values")
    session_id: Optional[str] = Field(None, description="Voice session ID")
    user_id: Optional[str] = Field(None, description="User ID for personalization")


class ConfirmActionRequest(BaseModel):
    confirmed: bool = Field(..., description="User confirmation (true/false)")


class ClarifyRequest(BaseModel):
    clarification_text: str = Field(..., description="Clarification question text")


class DialogStateResponse(BaseModel):
    state: str
    active_intent: Optional[str]
    slot_values: Dict[str, Any]
    context_stack_size: int
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]
    timeout: bool
    confirmation_question: Optional[str]
    clarification_question: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dialog/state", response_model=DialogStateResponse)
async def get_dialog_state(session_id: Optional[str] = None):
    """
    Get current dialog state.
    
    Args:
        session_id: Optional session filter (if multi-session support added)
    
    Returns:
        Current dialog state with confirmation/clarification questions
    """
    machine = get_dialog_machine()
    state = machine.get_state()
    
    # Check timeout
    timeout = machine.check_timeout()
    if timeout:
        machine.decay()
    
    return DialogStateResponse(
        state=state.state,
        active_intent=state.active_intent,
        slot_values=state.slot_values,
        context_stack_size=len(state.context_stack),
        last_activity_ts=state.last_activity_ts,
        session_id=state.session_id,
        user_id=state.user_id,
        timeout=timeout,
        confirmation_question=machine.generate_confirmation_question(),
        clarification_question=machine.generate_clarification_question(),
    )


@router.post("/dialog/activate", response_model=DialogStateResponse)
async def activate_intent(request: ActivateIntentRequest):
    """
    Activate new intent (push current to stack if active).
    
    Args:
        request: Intent, slots, session_id, user_id
    
    Returns:
        Updated dialog state
    """
    machine = get_dialog_machine()
    state = machine.activate_intent(
        intent=request.intent,
        slots=request.slots,
        session_id=request.session_id,
        user_id=request.user_id,
    )
    
    return DialogStateResponse(
        state=state.state,
        active_intent=state.active_intent,
        slot_values=state.slot_values,
        context_stack_size=len(state.context_stack),
        last_activity_ts=state.last_activity_ts,
        session_id=state.session_id,
        user_id=state.user_id,
        timeout=False,
        confirmation_question=None,
        clarification_question=None,
    )


@router.post("/dialog/confirm", response_model=DialogStateResponse)
async def confirm_action(request: ConfirmActionRequest):
    """
    User confirms or cancels pending action.
    
    Args:
        request: confirmed=true/false
    
    Returns:
        Updated dialog state (IDLE or restored from stack)
    """
    machine = get_dialog_machine()
    
    if request.confirmed:
        state = machine.confirm_action()
    else:
        state = machine.cancel_action()
    
    return DialogStateResponse(
        state=state.state,
        active_intent=state.active_intent,
        slot_values=state.slot_values,
        context_stack_size=len(state.context_stack),
        last_activity_ts=state.last_activity_ts,
        session_id=state.session_id,
        user_id=state.user_id,
        timeout=False,
        confirmation_question=None,
        clarification_question=None,
    )


@router.post("/dialog/cancel", response_model=DialogStateResponse)
async def cancel_action():
    """
    User cancels pending action.
    
    Returns:
        Updated dialog state (IDLE or restored from stack)
    """
    machine = get_dialog_machine()
    state = machine.cancel_action()
    
    return DialogStateResponse(
        state=state.state,
        active_intent=state.active_intent,
        slot_values=state.slot_values,
        context_stack_size=len(state.context_stack),
        last_activity_ts=state.last_activity_ts,
        session_id=state.session_id,
        user_id=state.user_id,
        timeout=False,
        confirmation_question=None,
        clarification_question=None,
    )


@router.post("/dialog/clarify", response_model=DialogStateResponse)
async def clarify_dialog(request: ClarifyRequest):
    """
    Set clarification question text.
    
    Args:
        request: clarification_text
    
    Returns:
        Updated dialog state with clarification question
    """
    machine = get_dialog_machine()
    state = machine.set_clarifying(request.clarification_text)
    
    return DialogStateResponse(
        state=state.state,
        active_intent=state.active_intent,
        slot_values=state.slot_values,
        context_stack_size=len(state.context_stack),
        last_activity_ts=state.last_activity_ts,
        session_id=state.session_id,
        user_id=state.user_id,
        timeout=False,
        confirmation_question=None,
        clarification_question=machine.generate_clarification_question(),
    )


@router.post("/dialog/timeout")
async def check_timeout():
    """
    Check and handle dialog timeout.
    
    Returns:
        {"timed_out": bool, "state": str}
    """
    machine = get_dialog_machine()
    timed_out = machine.check_timeout()
    
    if timed_out:
        machine.decay()
    
    return {
        "timed_out": timed_out,
        "state": machine.get_state().state,
    }


@router.post("/dialog/reset")
async def reset_dialog():
    """
    Reset dialog state to IDLE.
    
    Returns:
        {"state": "IDLE"}
    """
    machine = get_dialog_machine()
    machine.reset()
    
    return {"state": "IDLE"}
