"""Confidence-scored German voice intent parser."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Pattern

from .clarification_templates import build_german_clarification


@dataclass(frozen=True)
class IntentPattern:
    """Regex pattern with scoring metadata."""

    intent: str
    pattern: Pattern[str]
    required_slots: tuple[str, ...] = ()
    base_confidence: float = 0.75


@dataclass
class IntentParseResult:
    """Structured parse result with confidence and clarification metadata."""

    intent: str
    confidence: float
    raw_text: str
    normalized_text: str
    slots: Dict[str, Any] = field(default_factory=dict)
    missing_slots: List[str] = field(default_factory=list)
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None
    matched_pattern: Optional[str] = None
    suggested_intents: List[str] = field(default_factory=list)

    @property
    def domain(self) -> Optional[str]:
        if "." not in self.intent:
            return None
        return self.intent.split(".", 1)[0]

    @property
    def action(self) -> Optional[str]:
        if "." not in self.intent:
            return None
        return self.intent.split(".", 1)[1]


class IntentParser:
    """German-first parser for common home automation commands.

    Thresholds are intentionally aligned with the approved routing design:
    - high-confidence exact matches score near 0.90+
    - incomplete but recognisable commands land in the clarification band
    - unknown commands fall below the fallback threshold
    """

    def __init__(self) -> None:
        self._patterns: List[IntentPattern] = [
            IntentPattern(
                intent="light.turn_on",
                pattern=re.compile(
                    r"^(?:mach|schalte)\s+(?:das\s+)?licht(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?\s+(?:an|ein)$"
                ),
                required_slots=(),
                base_confidence=0.90,
            ),
            IntentPattern(
                intent="light.turn_on",
                pattern=re.compile(
                    r"^licht(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?\s+(?:an|ein)$"
                ),
                required_slots=(),
                base_confidence=0.82,
            ),
            IntentPattern(
                intent="light.turn_off",
                pattern=re.compile(
                    r"^(?:mach|schalte)\s+(?:das\s+)?licht(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?\s+aus$"
                ),
                required_slots=(),
                base_confidence=0.90,
            ),
            IntentPattern(
                intent="light.turn_off",
                pattern=re.compile(r"^licht(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?\s+aus$"),
                required_slots=(),
                base_confidence=0.82,
            ),
            IntentPattern(
                intent="light.set_brightness",
                pattern=re.compile(
                    r"^(?:dimme|stelle)\s+(?:das\s+)?licht(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?(?:\s+auf\s+(?P<brightness>\d{1,3}))?\s*(?:%|prozent)?$"
                ),
                required_slots=("brightness",),
                base_confidence=0.92,
            ),
            IntentPattern(
                intent="climate.set_temperature",
                pattern=re.compile(
                    r"^(?:stell(?:e)?|setze)\s+(?:die\s+)?temperatur(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?(?:\s+auf\s+(?P<target_temp>\d+(?:[\.,]\d+)?))\s*grad$"
                ),
                required_slots=("target_temp",),
                base_confidence=0.94,
            ),
            IntentPattern(
                intent="climate.set_temperature",
                pattern=re.compile(
                    r"^(?:stell(?:e)?|setze)\s+(?:die\s+)?temperatur(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?$"
                ),
                required_slots=("target_temp",),
                base_confidence=0.78,
            ),
            IntentPattern(
                intent="scene.activate",
                pattern=re.compile(r"^(?:aktiviere|starte)\s+(?:die\s+)?szene\s+(?P<scene>[\wäöüß\- ]+)$"),
                required_slots=("scene",),
                base_confidence=0.93,
            ),
            IntentPattern(
                intent="cover.open_cover",
                pattern=re.compile(
                    r"^(?:öffne|fahre)\s+(?:den\s+)?(?:rollladen|rollo)(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?(?:\s+hoch)?$"
                ),
                required_slots=(),
                base_confidence=0.89,
            ),
            IntentPattern(
                intent="cover.close_cover",
                pattern=re.compile(
                    r"^(?:schließe|fahre)\s+(?:den\s+)?(?:rollladen|rollo)(?:\s+im\s+(?P<room>[\wäöüß\- ]+?))?(?:\s+runter)?$"
                ),
                required_slots=(),
                base_confidence=0.89,
            ),
        ]

    def parse(self, text: str) -> IntentParseResult:
        """Parse German voice text into a structured intent result."""
        normalized = self._normalize_text(text)
        candidates: List[IntentParseResult] = []

        for definition in self._patterns:
            match = definition.pattern.search(normalized)
            if not match:
                continue

            slots = self._extract_slots(match.groupdict())
            missing_slots = [slot for slot in definition.required_slots if slot not in slots]
            confidence = self._score_match(
                normalized_text=normalized,
                matched_text=match.group(0),
                slots=slots,
                missing_slots=missing_slots,
                base_confidence=definition.base_confidence,
            )
            candidates.append(
                IntentParseResult(
                    intent=definition.intent,
                    confidence=confidence,
                    raw_text=text,
                    normalized_text=normalized,
                    slots=slots,
                    missing_slots=missing_slots,
                    clarification_needed=bool(missing_slots),
                    clarification_prompt=(
                        build_german_clarification(definition.intent, missing_slots, slots)
                        if missing_slots
                        else None
                    ),
                    matched_pattern=definition.pattern.pattern,
                    suggested_intents=[],
                )
            )

        if candidates:
            return max(candidates, key=lambda item: item.confidence)

        suggestions = self._infer_suggestions(normalized)
        return IntentParseResult(
            intent="unknown",
            confidence=0.25 if suggestions else 0.15,
            raw_text=text,
            normalized_text=normalized,
            clarification_needed=False,
            clarification_prompt=None,
            suggested_intents=suggestions,
        )

    def _normalize_text(self, text: str) -> str:
        normalized = text.strip().lower()
        normalized = normalized.replace("?", " ").replace("!", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _extract_slots(self, groupdict: Dict[str, Optional[str]]) -> Dict[str, Any]:
        slots: Dict[str, Any] = {}
        for key, value in groupdict.items():
            if value is None:
                continue
            clean = value.strip()
            if not clean:
                continue
            if key == "room":
                slots[key] = self._normalize_room(clean)
            elif key == "brightness":
                slots[key] = max(0, min(100, int(clean)))
            elif key == "target_temp":
                slots[key] = float(clean.replace(",", "."))
            else:
                slots[key] = clean
        return slots

    def _normalize_room(self, room: str) -> str:
        room = room.strip()
        room = re.sub(r"^(dem|den|der|die|das)\s+", "", room)
        return room

    def _score_match(
        self,
        normalized_text: str,
        matched_text: str,
        slots: Dict[str, Any],
        missing_slots: Iterable[str],
        base_confidence: float,
    ) -> float:
        confidence = base_confidence
        missing_count = len(list(missing_slots))
        confidence -= 0.16 * missing_count
        confidence += min(0.03 * len(slots), 0.09)
        if matched_text.strip() == normalized_text.strip():
            confidence += 0.03
        return round(max(0.05, min(0.99, confidence)), 2)

    def _infer_suggestions(self, normalized_text: str) -> List[str]:
        suggestions: List[str] = []
        if any(token in normalized_text for token in ("licht", "lampe")):
            suggestions.extend(["light.turn_on", "light.turn_off"])
        if "temperatur" in normalized_text or "heizung" in normalized_text:
            suggestions.append("climate.set_temperature")
        if "szene" in normalized_text:
            suggestions.append("scene.activate")
        if "rollladen" in normalized_text or "rollo" in normalized_text:
            suggestions.extend(["cover.open_cover", "cover.close_cover"])
        return suggestions
