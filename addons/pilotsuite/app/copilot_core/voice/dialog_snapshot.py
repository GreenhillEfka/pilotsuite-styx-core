"""Shared dialog snapshot projection helpers for voice flows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class DialogSnapshot:
    """Application-facing snapshot of dialog-machine state."""

    state: str
    active_intent: Optional[str]
    slot_values: dict[str, Any]
    context_stack_size: int
    last_activity_ts: Optional[float]
    session_id: Optional[str]
    user_id: Optional[str]
    last_status: str
    pending_confirmation: bool
    pending_action_label: Optional[str]
    pending_action_payload: Optional[dict[str, Any]]
    clarification_question: Optional[str]
    confirmation_token: Optional[str]
    confirmation_expires_at: Optional[Any]

    @classmethod
    def from_state(cls, state: Any) -> "DialogSnapshot":
        slot_values = dict(getattr(state, "slot_values", {}) or {})
        confirmation_token = slot_values.get("_confirmation_token")
        return cls(
            state=getattr(state, "state", "IDLE"),
            active_intent=getattr(state, "active_intent", None),
            slot_values=slot_values,
            context_stack_size=len(getattr(state, "context_stack", []) or []),
            last_activity_ts=getattr(state, "last_activity_ts", None),
            session_id=getattr(state, "session_id", None),
            user_id=getattr(state, "user_id", None),
            last_status=_normalize_last_status(getattr(state, "state", "IDLE"), slot_values),
            pending_confirmation=getattr(state, "state", "IDLE") == "CONFIRMING" and bool(confirmation_token),
            pending_action_label=slot_values.get("_pending_action_label"),
            pending_action_payload=slot_values.get("_pending_action_payload"),
            clarification_question=slot_values.get("_clarification"),
            confirmation_token=confirmation_token,
            confirmation_expires_at=slot_values.get("_confirmation_expires_at"),
        )

    def to_dialog_state_fields(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "last_status": self.last_status,
            "active_intent": self.active_intent,
            "slot_values": dict(self.slot_values),
            "context_stack_size": self.context_stack_size,
            "last_activity_ts": self.last_activity_ts,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "clarification_question": self.clarification_question,
            "pending_confirmation": self.pending_confirmation,
            "pending_action_label": self.pending_action_label,
            "pending_action_payload": self.pending_action_payload,
            "confirmation_token": self.confirmation_token,
            "confirmation_expires_at": self.confirmation_expires_at,
        }

    def to_dialog_mutation_state(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "active_intent": self.active_intent,
            "slot_values": dict(self.slot_values),
            "context_stack_size": self.context_stack_size,
            "last_activity_ts": self.last_activity_ts,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }

    def to_command_session_state(self) -> dict[str, Any]:
        return {
            "dialog_state": self.state,
            "active_intent": self.active_intent,
            "slot_values": dict(self.slot_values),
            "session_id": self.session_id,
            "user_id": self.user_id,
            "last_status": self.last_status,
            "pending_confirmation": self.pending_confirmation,
            "pending_action_label": self.pending_action_label,
            "pending_action_payload": self.pending_action_payload,
            "clarification_question": self.clarification_question,
            "confirmation_token": self.confirmation_token,
            "confirmation_expires_at": self.confirmation_expires_at,
        }

    def to_command_state(self, *, session_id: str) -> dict[str, Any]:
        if not self.session_id or self.session_id != session_id:
            return {
                "last_status": "idle",
                "pending_confirmation": False,
                "pending_action_label": None,
                "confirmation_expires_at": None,
            }

        return {
            "last_status": self.last_status,
            "pending_confirmation": self.pending_confirmation,
            "pending_action_label": self.pending_action_label,
            "confirmation_expires_at": _format_timestamp(self.confirmation_expires_at),
        }


def _normalize_last_status(state: str, slot_values: dict[str, Any]) -> str:
    explicit = slot_values.get("_last_status")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    fallback = {
        "ACTIVE": "executed",
        "CONFIRMING": "confirmation_required",
        "CLARIFYING": "clarification_required",
        "IDLE": "idle",
    }
    return fallback.get(state, "idle")


def _format_timestamp(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError, OverflowError):
        return None
