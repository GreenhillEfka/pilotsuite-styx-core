"""API v1 Service - User Hints with accept/reject and AutomationCreator bridge."""

from typing import Optional, List, Dict, Any
from .models import HintData, HintStatus, HintType
import logging
import uuid
import time

_LOGGER = logging.getLogger(__name__)


class UserHintsService:
    """User Hints Service - provides automation suggestions.

    Bridges the suggestion inbox with the AutomationCreator so that
    accepting a hint can create a real HA automation.
    """

    def __init__(self, automation_creator=None):
        """Initialize the service.

        Parameters
        ----------
        automation_creator : AutomationCreator, optional
            If provided, accepted suggestions are forwarded to the
            AutomationCreator to create real HA automations.
        """
        self._hints: Dict[str, HintData] = {}
        self._automation_creator = automation_creator

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_hints(self, status: Optional[HintStatus] = None) -> List[HintData]:
        """Get hints, optionally filtered by status."""
        if status:
            return [h for h in self._hints.values() if h.status == status]
        return [h for h in self._hints.values() if h.status == HintStatus.ACTIVE]

    async def add_hint(self, text: str, hint_type: Optional[HintType] = None) -> HintData:
        """Add a new hint from text."""
        hint_id = uuid.uuid4().hex[:12]
        hint = HintData(
            hint_id=hint_id,
            title=text[:80],
            description=text,
            hint_type=hint_type or HintType.SUGGESTION,
            status=HintStatus.ACTIVE,
            entity_ids=[],
            confidence=0.5,
            metadata={"created_at": time.time()},
        )
        self._hints[hint_id] = hint
        return hint

    async def dismiss_hint(self, hint_id: str) -> bool:
        """Dismiss a hint."""
        if hint_id in self._hints:
            self._hints[hint_id].status = HintStatus.DISMISSED
            return True
        return False

    async def get_hint_by_id(self, hint_id: str) -> Optional[HintData]:
        """Get a specific hint."""
        return self._hints.get(hint_id)

    def get_suggestions(self) -> List[HintData]:
        """Get all hints that are suggestions (for automation creation)."""
        return [
            h for h in self._hints.values()
            if h.hint_type in (HintType.AUTOMATION, HintType.SUGGESTION)
            and h.status == HintStatus.ACTIVE
        ]

    # ------------------------------------------------------------------
    # Accept / Reject
    # ------------------------------------------------------------------

    async def accept_suggestion(self, hint_id: str) -> bool:
        """Accept a suggestion and attempt to create an HA automation.

        If an AutomationCreator is available, the suggestion is forwarded
        to it. The hint status is set to DISMISSED regardless.
        """
        hint = self._hints.get(hint_id)
        if not hint:
            _LOGGER.warning("accept_suggestion: hint %s not found", hint_id)
            return False

        hint.status = HintStatus.DISMISSED
        hint.metadata["accepted"] = True
        hint.metadata["accepted_at"] = time.time()

        # Try to create automation via AutomationCreator
        if self._automation_creator:
            try:
                result = self._automation_creator.create_from_suggestion({
                    "antecedent": hint.title,
                    "consequent": hint.description,
                    "alias": f"PilotSuite: {hint.title[:50]}",
                })
                hint.metadata["automation_result"] = result
                if result.get("ok"):
                    _LOGGER.info(
                        "Accepted hint %s -> automation %s",
                        hint_id, result.get("automation_id"),
                    )
                else:
                    _LOGGER.warning(
                        "Hint %s accepted but automation creation failed: %s",
                        hint_id, result.get("error"),
                    )
            except Exception as exc:
                _LOGGER.exception("Error creating automation for hint %s", hint_id)
                hint.metadata["automation_error"] = str(exc)
        else:
            _LOGGER.info("Hint %s accepted (no AutomationCreator available)", hint_id)

        return True

    async def reject_suggestion(self, hint_id: str, reason: Optional[str] = None) -> bool:
        """Reject a suggestion with optional reason."""
        hint = self._hints.get(hint_id)
        if not hint:
            _LOGGER.warning("reject_suggestion: hint %s not found", hint_id)
            return False

        hint.status = HintStatus.DISMISSED
        hint.metadata["rejected"] = True
        hint.metadata["rejected_at"] = time.time()
        if reason:
            hint.metadata["reject_reason"] = reason

        _LOGGER.info("Hint %s rejected (reason: %s)", hint_id, reason or "none")
        return True
