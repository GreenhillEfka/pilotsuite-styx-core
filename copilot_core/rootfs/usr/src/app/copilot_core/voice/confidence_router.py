"""Three-tier routing for confidence-scored voice intents."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .clarification_templates import build_german_clarification
from .intent_parser import IntentParseResult


class RoutingDecision(str, Enum):
    """High-level action chosen for a parsed intent."""

    EXECUTE = "execute"
    CLARIFY = "clarify"
    FALLBACK = "fallback"


class ProcessingTier(str, Enum):
    """Approved three-tier processing path."""

    REGEX = "tier1_regex"
    ML = "tier2_ml"
    LLM = "tier3_llm"


@dataclass
class RouteResult:
    """Routing output consumed by dialog and execution layers."""

    decision: RoutingDecision
    processing_tier: ProcessingTier
    reason: str
    confidence: float
    clarification_prompt: Optional[str] = None
    suggested_intents: List[str] = field(default_factory=list)


class ConfidenceRouter:
    """Apply routing thresholds documented in the approved design.

    Thresholds:
    - >= 0.85: execute directly through deterministic regex path
    - 0.60-0.84: ask clarifying question / resolve ambiguity
    - < 0.60: fall back to broader ML/LLM handling
    """

    DIRECT_THRESHOLD = 0.85
    CLARIFY_THRESHOLD = 0.60
    MIN_KNOWN_INTENT_THRESHOLD = 0.45

    def route(self, parsed: IntentParseResult) -> RouteResult:
        """Choose execute, clarify, or fallback for a parse result."""
        if parsed.intent == "unknown":
            return RouteResult(
                decision=RoutingDecision.FALLBACK,
                processing_tier=ProcessingTier.LLM,
                reason="unknown_intent",
                confidence=parsed.confidence,
                suggested_intents=parsed.suggested_intents,
            )

        if parsed.missing_slots and parsed.confidence >= self.MIN_KNOWN_INTENT_THRESHOLD:
            return RouteResult(
                decision=RoutingDecision.CLARIFY,
                processing_tier=ProcessingTier.ML,
                reason="missing_slots",
                confidence=parsed.confidence,
                clarification_prompt=parsed.clarification_prompt
                or build_german_clarification(parsed.intent, parsed.missing_slots, parsed.slots),
                suggested_intents=parsed.suggested_intents,
            )

        if parsed.confidence >= self.DIRECT_THRESHOLD:
            return RouteResult(
                decision=RoutingDecision.EXECUTE,
                processing_tier=ProcessingTier.REGEX,
                reason="high_confidence",
                confidence=parsed.confidence,
                suggested_intents=parsed.suggested_intents,
            )

        if parsed.confidence >= self.CLARIFY_THRESHOLD:
            return RouteResult(
                decision=RoutingDecision.CLARIFY,
                processing_tier=ProcessingTier.ML,
                reason="medium_confidence",
                confidence=parsed.confidence,
                clarification_prompt=parsed.clarification_prompt
                or build_german_clarification(parsed.intent, parsed.missing_slots, parsed.slots),
                suggested_intents=parsed.suggested_intents,
            )

        return RouteResult(
            decision=RoutingDecision.FALLBACK,
            processing_tier=ProcessingTier.LLM,
            reason="low_confidence",
            confidence=parsed.confidence,
            suggested_intents=parsed.suggested_intents,
        )
