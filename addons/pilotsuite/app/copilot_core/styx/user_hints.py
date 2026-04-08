# Migrated from pilotsuite-styx-ha
"""User Hints NLP Engine — pure text processing, no HA dependencies.

Parses German-language user hints and classifies them into automation
suggestions. Entity resolution returns entity NAMES (strings);
HA-side performs the actual entity_id lookup.
"""

import re
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from .user_hints_models import (
    UserHint,
    HintStatus,
    HintType,
    HintSuggestion,
)


class UserHintsEngine:
    """Pure NLP engine for user hint parsing and suggestion generation.

    Sync class — no async needed for text processing.
    No HA dependencies; operates on plain text and returns entity names.
    """

    # ------------------------------------------------------------------ #
    # German NLP regex patterns
    # ------------------------------------------------------------------ #

    SYNC_PATTERNS = [
        r"schalte?\s+(\w+)\s+(?:immer\s+)?sync(?:hron)?\s+mit\s+(\w+)",
        r"(\w+)\s+(?:und|mit)\s+(\w+)\s+(?:zusammen|gleichzeitig)",
        r"wenn\s+(\w+)\s+(?:dann\s+)?auch\s+(\w+)",
    ]

    SCHEDULE_PATTERNS = [
        r"um\s+(\d{1,2}[:.]\d{2})",
        r"(\d{1,2})\s* Uhr",
        r"morgens?|abends?|mittags?",
        r"bei\s+(sonnenaufgang|sonnenuntergang)",
    ]

    ENTITY_PATTERNS = [
        r"(kaffee(?:maschine|mühle|hahn))",
        r"(licht|lampe|beleuchtung)[\s_-]?(\w+)",
        r"(heizung|thermostat)[\s_-]?(\w+)",
        r"(rollladen|rollo|vorhang)[\s_-]?(\w+)",
        r"(musik|lautsprecher|sonos)[\s_-]?(\w+)",
    ]

    # ------------------------------------------------------------------ #
    # Constructor
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        self._hints: Dict[str, UserHint] = {}
        self._suggestions: Dict[str, HintSuggestion] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyze_text(self, text: str, hint_type: Optional[HintType] = None) -> UserHint:
        """Main entry point: parse text into a UserHint with NLP analysis.

        Args:
            text: Raw German-language user input.
            hint_type: Optional override; auto-detected when ``None``.

        Returns:
            Fully analyzed ``UserHint`` instance.
        """
        hint_id = str(uuid.uuid4())[:8]

        if hint_type is None:
            hint_type = self._detect_hint_type(text)

        hint = UserHint(
            id=hint_id,
            text=text,
            hint_type=hint_type,
        )

        self._analyze_hint(hint)

        self._hints[hint_id] = hint
        return hint

    def get_hints(self, status: Optional[HintStatus] = None) -> List[UserHint]:
        """Return all stored hints, optionally filtered by status."""
        hints = list(self._hints.values())
        if status:
            hints = [h for h in hints if h.status == status]
        return sorted(hints, key=lambda h: h.created_at, reverse=True)

    def get_suggestions(self) -> List[HintSuggestion]:
        """Return all generated suggestions."""
        return list(self._suggestions.values())

    # ------------------------------------------------------------------ #
    # Hint type detection
    # ------------------------------------------------------------------ #

    def _detect_hint_type(self, text: str) -> HintType:
        """Classify free-form text into a ``HintType``."""
        text_lower = text.lower()

        # Check for automation / sync patterns
        if any(re.search(p, text_lower) for p in self.SYNC_PATTERNS):
            return HintType.AUTOMATION

        # Check for schedule patterns
        if any(re.search(p, text_lower) for p in self.SCHEDULE_PATTERNS):
            return HintType.SCHEDULE

        # Preference keywords
        if any(word in text_lower for word in ["nicht", "nie", "stört", "nervt"]):
            return HintType.PREFERENCE

        # Feature-request keywords
        if any(word in text_lower for word in ["wünsche", "möchte", "brauche", "fehlt"]):
            return HintType.FEATURE_REQUEST

        # Default
        return HintType.AUTOMATION

    # ------------------------------------------------------------------ #
    # Hint analysis
    # ------------------------------------------------------------------ #

    def _analyze_hint(self, hint: UserHint) -> None:
        """Extract entities, actions, conditions and schedule from hint text."""
        text_lower = hint.text.lower()

        # --- entity extraction ---
        entities: List[str] = []
        for pattern in self.ENTITY_PATTERNS:
            matches = re.findall(pattern, text_lower)
            entities.extend(
                "_".join(m) if isinstance(m, tuple) else m for m in matches
            )

        # Extract from sync patterns (captures paired entity names)
        for pattern in self.SYNC_PATTERNS:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if isinstance(match, tuple):
                    entities.extend(list(match))
                else:
                    entities.append(match)

        hint.entities = list(set(entities))

        # --- action extraction ---
        if "schalte" in text_lower or "einschalten" in text_lower:
            hint.actions.append("turn_on")
        if "ausschalten" in text_lower:
            hint.actions.append("turn_off")
        if "sync" in text_lower or "synchron" in text_lower:
            hint.actions.append("sync")

        # --- schedule extraction ---
        for pattern in self.SCHEDULE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                hint.schedule = match.group(0)
                break

        # --- suggestion generation (entity-name based, no HA lookup) ---
        if len(hint.entities) >= 2 and hint.actions:
            self._generate_suggestion(hint)

        hint.status = HintStatus.ANALYZED
        hint.analyzed_at = datetime.now()

    # ------------------------------------------------------------------ #
    # Suggestion generation
    # ------------------------------------------------------------------ #

    def _generate_suggestion(self, hint: UserHint) -> None:
        """Generate an automation suggestion from analyzed hint data.

        Uses entity *names* (not HA entity_ids). HA-side resolves names
        to real entity_ids before creating automations.
        """
        if len(hint.entities) < 2:
            return

        entity1, entity2 = hint.entities[0], hint.entities[1]

        # Build suggestion with entity names — HA will resolve to entity_ids
        if hint.hint_type == HintType.AUTOMATION:
            suggestion = HintSuggestion(
                hint_id=hint.id,
                name=f"Sync {entity1} mit {entity2}",
                description=f"Automatisierung basierend auf: {hint.text}",
                trigger={
                    "platform": "state",
                    "entity_name": entity1,
                    "to": "on",
                },
                action={
                    "service": "homeassistant.turn_on",
                    "target": {"entity_name": entity2},
                },
                confidence=0.8,
                reasoning=f"Erkannte Beziehung zwischen {entity1} und {entity2}",
            )

            hint.suggested_automation = suggestion.to_dict()
            hint.confidence = 0.8
            hint.status = HintStatus.SUGGESTION_CREATED

            self._suggestions[hint.id] = suggestion
