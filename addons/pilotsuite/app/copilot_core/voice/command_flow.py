"""Application-facing command-flow service for voice command routing."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Generic, TypeVar, Optional

from copilot_core.voice.voice_handler import VoiceResponse


T = TypeVar("T")


@dataclass(frozen=True)
class CommandProcessResult:
    """Bounded result of VoiceCommandFlow.process()."""
    status: str
    action: Optional[str]
    message: Optional[str]
    confirmation_token: Optional[str]
    session_state: dict[str, Any]
    intent: dict[str, Any]
    context: dict[str, Any]
    effective_confidence: float
    response: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "message": self.message,
            "confirmation_token": self.confirmation_token,
            "session_state": self.session_state,
            "intent": self.intent,
            "context": self.context,
            "effective_confidence": self.effective_confidence,
            **({"response": self.response} if self.response is not None else {}),
        }


@dataclass(frozen=True)
class CommandStateResult:
    """Bounded result of VoiceCommandFlow.get_state()."""
    status: str
    session_id: str
    state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "session_id": self.session_id,
            "state": self.state,
        }


@dataclass(frozen=True)
class CommandConfirmResult:
    """Bounded result of VoiceCommandFlow.confirm()."""
    status: str
    action: Optional[str]
    message: Optional[str]
    confirmation_token: str
    session_state: dict[str, Any]
    response: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "message": self.message,
            "confirmation_token": self.confirmation_token,
            "session_state": self.session_state,
            **({"response": self.response} if self.response is not None else {}),
        }


@dataclass(frozen=True)
class CommandRejectResult:
    """Bounded result of VoiceCommandFlow.reject()."""
    status: str
    action: Optional[str]
    message: str
    confirmation_token: str
    session_state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "message": self.message,
            "confirmation_token": self.confirmation_token,
            "session_state": self.session_state,
        }


class VoiceCommandFlow:
    """Own the command-flow procedure behind the HTTP adapter."""

    def __init__(
        self,
        *,
        intent_handler: Any,
        context_builder: Any,
        command_router: Any,
        dialog_machine: Any,
        dialog_state_serializer: Optional[Callable[[Any], Dict[str, Any]]] = None,
    ):
        self._intent_handler = intent_handler
        self._context_builder = context_builder
        self._command_router = command_router
        self._dialog_machine = dialog_machine
        self._dialog_state_serializer = dialog_state_serializer or self._default_dialog_state_serializer

    def process(
        self,
        *,
        utterance: str,
        confidence: Optional[float],
        intent_candidates: Optional[list[Any]],
        session_id: Optional[str],
        user_id: Optional[str],
        zone_id: Optional[str],
        request_context: Optional[Dict[str, Any]] = None,
    ) -> CommandProcessResult:
        request_context = request_context or {}
        user_preferences = request_context.get("user_preferences")
        active_devices = request_context.get("active_devices")

        context = self._context_builder.build_context(
            mood_engine=self._intent_handler.mood_engine,
            habitus_service=self._intent_handler.habitus_service,
            zone_name=zone_id,
            force_refresh=bool(request_context),
            user_preferences=user_preferences,
            active_devices=active_devices,
        )

        routed = self._command_router.route(
            utterance=utterance,
            stt_confidence=confidence,
            context=context,
            intent_candidates=intent_candidates,
            session_id=session_id,
            user_id=user_id,
            zone_id=zone_id,
        )

        decision = routed["decision"]
        normalized_intent = routed["normalized_intent"]
        intent_name = normalized_intent.value if hasattr(normalized_intent, "value") else str(normalized_intent)

        state = self._apply_decision(
            decision=decision,
            intent_name=intent_name,
            utterance=utterance,
            session_id=session_id,
            user_id=user_id,
        )
        state = self._dialog_machine.merge_metadata({"_last_status": decision.status})

        session_state = dict(getattr(decision, "session_state", {}) or {})
        session_state.update(self._dialog_state_serializer(state))

        response_dict = None
        if routed.get("response") is not None:
            response_dict = routed["response"].to_dict()

        return CommandProcessResult(
            status=decision.status,
            action=decision.action,
            message=decision.message,
            confirmation_token=decision.confirmation_token,
            session_state=session_state,
            intent=routed["intent"].to_dict(),
            context=context.to_dict(),
            effective_confidence=routed["effective_confidence"],
            response=response_dict,
        )

    def get_state(self, *, session_id: str) -> CommandStateResult:
        if self._dialog_machine.check_timeout():
            self._dialog_machine.decay()
        state = self._dialog_machine.get_state()
        return CommandStateResult(
            status="ok",
            session_id=session_id,
            state=self._serialize_command_state(state, session_id=session_id),
        )

    def confirm(self, *, session_id: str, confirmation_token: str) -> CommandConfirmResult:
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
        response = self._build_follow_through_response(action_payload)

        return CommandConfirmResult(
            status="executed",
            action=action_label,
            message=response.tts_text,
            confirmation_token=confirmation_token,
            session_state=self._dialog_state_serializer(state),
            response=response.to_dict(),
        )

    def reject(self, *, session_id: str, confirmation_token: str) -> CommandRejectResult:
        pending = self._validate_pending_confirmation(
            session_id=session_id,
            confirmation_token=confirmation_token,
        )
        if pending is None:
            raise ValueError("No matching pending confirmation found")

        action_label = pending["action_label"]
        state = self._dialog_machine.cancel_action()
        state = self._dialog_machine.merge_metadata({"_last_status": "rejected"})

        return CommandRejectResult(
            status="rejected",
            action=action_label,
            message="Okay, ich verwerfe die angefragte Aktion.",
            confirmation_token=confirmation_token,
            session_state=self._dialog_state_serializer(state),
        )

    def _apply_decision(
        self,
        *,
        decision: Any,
        intent_name: str,
        utterance: str,
        session_id: Optional[str],
        user_id: Optional[str],
    ):
        if decision.status == "executed":
            return self._dialog_machine.activate_intent(
                intent=decision.action or intent_name,
                slots={"_last_utterance": utterance},
                session_id=session_id,
                user_id=user_id,
            )

        if decision.status == "confirmation_required":
            self._dialog_machine.activate_intent(
                intent=decision.action or intent_name,
                slots={"_last_utterance": utterance},
                session_id=session_id,
                user_id=user_id,
            )
            return self._dialog_machine.set_confirming(
                metadata={
                    "_last_utterance": utterance,
                    "_pending_action": decision.action,
                    "_pending_action_label": decision.action,
                    "_pending_action_payload": decision.action_payload,
                    "_confirmation_prompt": decision.message,
                    "_confirmation_expires_at": time.time() + self._dialog_machine.TIMEOUT_SECONDS,
                    "_confirmation_token": decision.confirmation_token,
                }
            )

        if decision.status == "clarification_required":
            self._dialog_machine.activate_intent(
                intent=intent_name,
                slots={"_last_utterance": utterance},
                session_id=session_id,
                user_id=user_id,
            )
            return self._dialog_machine.set_clarifying(
                decision.message,
                metadata={
                    "_last_utterance": utterance,
                    "_intent": intent_name,
                },
            )

        return self._dialog_machine.reset(session_id=session_id, user_id=user_id)

    @staticmethod
    def _default_dialog_state_serializer(state) -> Dict[str, Any]:
        slot_values = dict(state.slot_values)
        return {
            "dialog_state": state.state,
            "active_intent": state.active_intent,
            "slot_values": slot_values,
            "session_id": state.session_id,
            "user_id": state.user_id,
            "last_status": slot_values.get("_last_status"),
            "pending_confirmation": state.state == "CONFIRMING" and bool(slot_values.get("_confirmation_token")),
            "pending_action_label": slot_values.get("_pending_action_label"),
            "pending_action_payload": slot_values.get("_pending_action_payload"),
            "clarification_question": slot_values.get("_clarification"),
            "confirmation_token": slot_values.get("_confirmation_token"),
            "confirmation_expires_at": slot_values.get("_confirmation_expires_at"),
        }

    def _validate_pending_confirmation(
        self,
        *,
        session_id: Optional[str],
        confirmation_token: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if self._dialog_machine.check_timeout():
            self._dialog_machine.decay()
            return None

        state = self._dialog_machine.get_state()
        if state.state != "CONFIRMING":
            return None

        slot_values = dict(state.slot_values)
        pending_token = slot_values.get("_confirmation_token")
        pending_session_id = state.session_id

        if not confirmation_token or confirmation_token != pending_token:
            return None
        if pending_session_id and session_id and session_id != pending_session_id:
            return None

        return {
            "state": state,
            "slot_values": slot_values,
            "action_payload": slot_values.get("_pending_action_payload"),
            "action_label": slot_values.get("_pending_action_label") or slot_values.get("_pending_action"),
        }

    def _serialize_command_state(self, state: Any, *, session_id: str) -> Dict[str, Any]:
        if not state.session_id or state.session_id != session_id:
            return {
                "last_status": "idle",
                "pending_confirmation": False,
                "pending_action_label": None,
                "confirmation_expires_at": None,
            }

        slot_values = dict(state.slot_values)
        pending_confirmation = state.state == "CONFIRMING" and bool(slot_values.get("_confirmation_token"))
        return {
            "last_status": self._normalize_last_status(state),
            "pending_confirmation": pending_confirmation,
            "pending_action_label": slot_values.get("_pending_action_label"),
            "confirmation_expires_at": self._format_command_state_timestamp(slot_values.get("_confirmation_expires_at")),
        }

    @staticmethod
    def _normalize_last_status(state: Any) -> str:
        slot_values = dict(state.slot_values)
        explicit = slot_values.get("_last_status")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()

        fallback = {
            "ACTIVE": "executed",
            "CONFIRMING": "confirmation_required",
            "CLARIFYING": "clarification_required",
            "IDLE": "idle",
        }
        return fallback.get(state.state, "idle")

    @staticmethod
    def _format_command_state_timestamp(value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OSError, OverflowError):
            return None

    @staticmethod
    def _build_follow_through_response(action_payload: Optional[Dict[str, Any]]) -> VoiceResponse:
        actions = [dict(action_payload)] if action_payload else []
        return VoiceResponse(
            tts_text="Bestätigt. Ich führe die Aktion jetzt aus.",
            actions=actions,
            confidence=1.0,
            language="de",
        )
