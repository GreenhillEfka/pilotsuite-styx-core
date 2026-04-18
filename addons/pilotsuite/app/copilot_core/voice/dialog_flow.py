"""Application-facing dialog-flow service for voice dialog routes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from copilot_core.voice.dialog_snapshot import DialogSnapshot


@dataclass(frozen=True)
class DialogStateResult:
    """Bounded result of VoiceDialogFlow.get_state()."""

    status: str
    state: str
    last_status: str
    active_intent: Optional[str]
    slot_values: dict[str, Any]
    context_stack_size: int
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]
    timed_out: bool
    confirmation_question: Optional[str]
    clarification_question: Optional[str]
    pending_confirmation: bool
    pending_action_label: Optional[str]
    pending_action_payload: Optional[dict[str, Any]]
    confirmation_token: Optional[str]
    confirmation_expires_at: Optional[Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "state": self.state,
            "last_status": self.last_status,
            "active_intent": self.active_intent,
            "slot_values": self.slot_values,
            "context_stack_size": self.context_stack_size,
            "last_activity_ts": self.last_activity_ts,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timed_out": self.timed_out,
            "confirmation_question": self.confirmation_question,
            "clarification_question": self.clarification_question,
            "pending_confirmation": self.pending_confirmation,
            "pending_action_label": self.pending_action_label,
            "pending_action_payload": self.pending_action_payload,
            "confirmation_token": self.confirmation_token,
            "confirmation_expires_at": self.confirmation_expires_at,
        }


@dataclass(frozen=True)
class DialogActivateResult:
    """Bounded result of VoiceDialogFlow.activate_intent()."""

    status: str
    state: str
    active_intent: Optional[str]
    slot_values: dict[str, Any]
    context_stack_size: int
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "state": self.state,
            "active_intent": self.active_intent,
            "slot_values": self.slot_values,
            "context_stack_size": self.context_stack_size,
            "last_activity_ts": self.last_activity_ts,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }


@dataclass(frozen=True)
class DialogConfirmResult:
    """Bounded result of VoiceDialogFlow.confirm_action()."""

    status: str
    state: str
    active_intent: Optional[str]
    slot_values: dict[str, Any]
    context_stack_size: int
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "state": self.state,
            "active_intent": self.active_intent,
            "slot_values": self.slot_values,
            "context_stack_size": self.context_stack_size,
            "last_activity_ts": self.last_activity_ts,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }


@dataclass(frozen=True)
class DialogClarifyResult:
    """Bounded result of VoiceDialogFlow.clarify()."""

    status: str
    state: str
    active_intent: Optional[str]
    slot_values: dict[str, Any]
    context_stack_size: int
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]
    clarification_question: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "state": self.state,
            "active_intent": self.active_intent,
            "slot_values": self.slot_values,
            "context_stack_size": self.context_stack_size,
            "last_activity_ts": self.last_activity_ts,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "clarification_question": self.clarification_question,
        }


@dataclass(frozen=True)
class DialogResetResult:
    """Bounded result of VoiceDialogFlow.reset()."""

    status: str
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "state": self.state,
        }


@dataclass(frozen=True)
class DialogConfirmTransitionResult:
    """Bounded result of VoiceDialogFlow.confirm_transition()."""

    status: str
    action: Optional[str]
    action_label: Optional[str]
    action_payload: Optional[dict[str, Any]]
    message: str
    new_state: str
    session_id: Optional[str]
    user_id: Optional[str]
    confirmation_token: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "action_label": self.action_label,
            "action_payload": self.action_payload,
            "message": self.message,
            "new_state": self.new_state,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "confirmation_token": self.confirmation_token,
        }


@dataclass(frozen=True)
class DialogRejectTransitionResult:
    """Bounded result of VoiceDialogFlow.reject_transition()."""

    status: str
    action: Optional[str]
    action_label: Optional[str]
    message: str
    new_state: str
    session_id: Optional[str]
    user_id: Optional[str]
    confirmation_token: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "action_label": self.action_label,
            "message": self.message,
            "new_state": self.new_state,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "confirmation_token": self.confirmation_token,
        }


class VoiceDialogFlow:
    """Own the dialog-state read and mutation procedures behind the HTTP adapter."""

    def __init__(self, *, dialog_machine: Any):
        self._dialog_machine = dialog_machine

    def get_state(self) -> DialogStateResult:
        state = self._dialog_machine.get_state()
        timed_out = self._dialog_machine.check_timeout()
        if timed_out:
            self._dialog_machine.decay()
            state = self._dialog_machine.get_state()

        snapshot = DialogSnapshot.from_state(state)
        return DialogStateResult(
            status="ok",
            timed_out=timed_out,
            confirmation_question=self._dialog_machine.generate_confirmation_question(),
            **snapshot.to_dialog_state_fields(),
        )

    def activate_intent(
        self,
        *,
        intent: str,
        slots: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> DialogActivateResult:
        state = self._dialog_machine.activate_intent(
            intent=intent,
            slots=slots or {},
            session_id=session_id,
            user_id=user_id,
        )
        return DialogActivateResult(status="ok", **DialogSnapshot.from_state(state).to_dialog_mutation_state())

    def confirm_action(self, *, confirmed: bool) -> DialogConfirmResult:
        state = self._dialog_machine.confirm_action() if confirmed else self._dialog_machine.cancel_action()
        return DialogConfirmResult(status="ok", **DialogSnapshot.from_state(state).to_dialog_mutation_state())

    def clarify(self, *, clarification_text: str) -> DialogClarifyResult:
        state = self._dialog_machine.set_clarifying(clarification_text)
        snapshot = DialogSnapshot.from_state(state)
        return DialogClarifyResult(
            status="ok",
            clarification_question=self._dialog_machine.generate_clarification_question(),
            **snapshot.to_dialog_mutation_state(),
        )

    def reset(
        self,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> DialogResetResult:
        state = self._dialog_machine.reset(session_id=session_id, user_id=user_id)
        return DialogResetResult(status="ok", state=state.state)

    def confirm_transition(
        self,
        *,
        session_id: Optional[str],
        confirmation_token: str,
    ) -> DialogConfirmTransitionResult:
        """Handle confirm transition with token validation, expiry check, and state mutation."""
        pending = self._validate_pending_confirmation(
            session_id=session_id,
            confirmation_token=confirmation_token,
        )
        if pending is None:
            raise ValueError("No matching pending confirmation found")

        action_payload = pending["action_payload"]
        action_label = pending["action_label"]
        state = self._dialog_machine.confirm_action()
        state = self._dialog_machine.merge_metadata({"_last_status": "executed"})
        snapshot = DialogSnapshot.from_state(state)

        return DialogConfirmTransitionResult(
            status="executed",
            action=pending.get("action"),
            action_label=action_label,
            action_payload=action_payload,
            message="Bestätigt. Ich führe die Aktion jetzt aus.",
            new_state=state.state,
            session_id=state.session_id,
            user_id=state.user_id,
            confirmation_token=confirmation_token,
        )

    def reject_transition(
        self,
        *,
        session_id: Optional[str],
        confirmation_token: str,
    ) -> DialogRejectTransitionResult:
        """Handle reject transition with token validation, expiry check, and state mutation."""
        pending = self._validate_pending_confirmation(
            session_id=session_id,
            confirmation_token=confirmation_token,
        )
        if pending is None:
            raise ValueError("No matching pending confirmation found")

        action_label = pending["action_label"]
        state = self._dialog_machine.cancel_action()
        state = self._dialog_machine.merge_metadata({"_last_status": "rejected"})
        snapshot = DialogSnapshot.from_state(state)

        return DialogRejectTransitionResult(
            status="rejected",
            action=pending.get("action"),
            action_label=action_label,
            message="Okay, ich verwerfe die angefragte Aktion.",
            new_state=state.state,
            session_id=state.session_id,
            user_id=state.user_id,
            confirmation_token=confirmation_token,
        )

    def _validate_pending_confirmation(
        self,
        *,
        session_id: Optional[str],
        confirmation_token: Optional[str],
    ) -> Optional[dict[str, Any]]:
        """Validate pending confirmation with timeout, token, and session checks."""
        import time

        if self._dialog_machine.check_timeout():
            self._dialog_machine.decay()
            return None

        state = self._dialog_machine.get_state()
        if state.state != "CONFIRMING":
            return None

        slot_values = dict(state.slot_values)
        pending_token = slot_values.get("_confirmation_token")
        pending_session_id = state.session_id
        expires_at = slot_values.get("_confirmation_expires_at")

        # Check expiry
        if expires_at is not None and time.time() > expires_at:
            return None

        if not confirmation_token or confirmation_token != pending_token:
            return None
        if pending_session_id and session_id and session_id != pending_session_id:
            return None

        return {
            "state": state,
            "slot_values": slot_values,
            "action": slot_values.get("_pending_action"),
            "action_payload": slot_values.get("_pending_action_payload"),
            "action_label": slot_values.get("_pending_action_label") or slot_values.get("_pending_action"),
        }
