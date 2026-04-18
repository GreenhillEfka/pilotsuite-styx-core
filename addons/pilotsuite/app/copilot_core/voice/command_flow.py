"""Application-facing command-flow service for voice command routing."""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional


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
    ) -> Dict[str, Any]:
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

        response_payload = {
            "status": decision.status,
            "action": decision.action,
            "message": decision.message,
            "confirmation_token": decision.confirmation_token,
            "session_state": session_state,
            "intent": routed["intent"].to_dict(),
            "context": context.to_dict(),
            "effective_confidence": routed["effective_confidence"],
        }
        if routed.get("response") is not None:
            response_payload["response"] = routed["response"].to_dict()

        return response_payload

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
