"""Predictive Automation Engine — Slice 14.

Predicts user intent and pre-emptively prepares automations.

Features:
- Pattern recognition (time, presence, weather, calendar)
- Predictive proposals (before user asks)
- Confidence scoring + user feedback loop
- Seasonal adaptation
- Machine learning from user behavior
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Type of recognized pattern."""
    TIME_BASED = "time_based"  # Recurring at specific time
    PRESENCE_BASED = "presence_based"  # Triggered by presence
    WEATHER_BASED = "weather_based"  # Triggered by weather
    CALENDAR_BASED = "calendar_based"  # Triggered by calendar events
    SEASONAL = "seasonal"  # Seasonal patterns
    BEHAVIORAL = "behavioral"  # Learned from user behavior


class PredictionConfidence(Enum):
    """Confidence level for predictions."""
    VERY_LOW = "very_low"  # < 20%
    LOW = "low"  # 20-40%
    MEDIUM = "medium"  # 40-60%
    HIGH = "high"  # 60-80%
    VERY_HIGH = "very_high"  # > 80%


@dataclass
class BehavioralPattern:
    """Recognized behavioral pattern."""
    pattern_id: str
    pattern_type: PatternType
    zone_id: str
    module_id: str
    entity_id: str
    trigger_conditions: Dict[str, Any]
    typical_action: Dict[str, Any]
    occurrence_count: int = 0
    last_triggered: Optional[str] = None
    confidence: PredictionConfidence = PredictionConfidence.LOW
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "BehavioralPatternV1",
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "entity_id": self.entity_id,
            "trigger_conditions": self.trigger_conditions,
            "typical_action": self.typical_action,
            "occurrence_count": self.occurrence_count,
            "last_triggered": self.last_triggered,
            "confidence": self.confidence.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class PredictiveProposal:
    """Predictive automation proposal."""
    proposal_id: str
    pattern_id: str
    zone_id: str
    module_id: str
    description: str
    predicted_action: Dict[str, Any]
    confidence: PredictionConfidence
    confidence_score: float  # 0.0-1.0
    reasoning: str  # Why this prediction was made
    expires_at: str
    accepted: bool = False
    rejected: bool = False
    feedback: Optional[str] = None
    source_signals: List[str] = field(default_factory=list)
    policy_gate_required: bool = True
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": "PredictiveProposalV1",
            "proposal_id": self.proposal_id,
            "pattern_id": self.pattern_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "description": self.description,
            "predicted_action": self.predicted_action,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "expires_at": self.expires_at,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "feedback": self.feedback,
            "source_signals": list(self.source_signals),
            "policy_gate_required": self.policy_gate_required,
            "evidence": dict(self.evidence),
        }


class PredictiveAutomationEngine:
    """Main predictive automation engine."""
    
    def __init__(self):
        self._patterns: Dict[str, BehavioralPattern] = {}
        self._proposals: Dict[str, PredictiveProposal] = {}
        self._pattern_counter = 0
        self._proposal_counter = 0
        
        # Pattern detection thresholds
        self._min_occurrences_for_pattern = 3  # Need 3 occurrences to form pattern
        self._min_confidence_for_proposal = 0.6  # 60% confidence to propose
        self._pattern_decay_days = 30  # Patterns decay after 30 days
        
        # Context tracking
        self._recent_actions: List[Dict[str, Any]] = []
        self._context_window_hours = 24 * 30

    def _normalize_timestamp(self, value: Any) -> str:
        """Normalize timestamps to timezone-aware ISO format."""
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str) and value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.now(timezone.utc)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).isoformat()

    def record_action(self, action: Dict[str, Any]) -> None:
        """Record a user action for pattern learning."""
        action_timestamp = self._normalize_timestamp(action.get("timestamp"))
        self._recent_actions.append({
            **action,
            "timestamp": action_timestamp,
        })
        
        # Trim to context window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._context_window_hours)
        self._recent_actions = [
            a for a in self._recent_actions
            if datetime.fromisoformat(a["timestamp"]) > cutoff
        ]
        
        # Try to detect patterns
        self._detect_patterns()
    
    def _detect_patterns(self) -> None:
        """Detect behavioral patterns from recent actions."""
        # Group actions by entity and time pattern
        entity_actions: Dict[str, List[Dict[str, Any]]] = {}
        
        for action in self._recent_actions:
            entity_id = action.get("entity_id")
            if not entity_id:
                continue
            
            if entity_id not in entity_actions:
                entity_actions[entity_id] = []
            entity_actions[entity_id].append(action)
        
        # Look for patterns
        for entity_id, actions in entity_actions.items():
            if len(actions) < self._min_occurrences_for_pattern:
                continue
            
            # Detect time-based pattern
            self._detect_time_pattern(entity_id, actions)
            
            # Detect presence-based pattern
            self._detect_presence_pattern(entity_id, actions)

            # Detect calendar-based pattern
            self._detect_calendar_pattern(entity_id, actions)
    
    def _detect_time_pattern(self, entity_id: str, actions: List[Dict[str, Any]]) -> None:
        """Detect time-based patterns."""
        # Extract hours from actions
        hours = []
        for action in actions:
            ts = datetime.fromisoformat(action["timestamp"])
            hours.append(ts.hour)
        
        if not hours:
            return
        
        # Check if actions cluster around specific hour
        avg_hour = sum(hours) / len(hours)
        hour_stddev = (sum((h - avg_hour) ** 2 for h in hours) / len(hours)) ** 0.5
        
        # If stddev is low (< 2 hours), we have a time pattern
        if hour_stddev < 2.0:
            pattern_id = f"time_pattern_{entity_id}_{int(avg_hour)}"
            
            if pattern_id not in self._patterns:
                self._pattern_counter += 1
                self._patterns[pattern_id] = BehavioralPattern(
                    pattern_id=pattern_id,
                    pattern_type=PatternType.TIME_BASED,
                    zone_id=actions[0].get("zone_id", "unknown"),
                    module_id=actions[0].get("module_id", "unknown"),
                    entity_id=entity_id,
                    trigger_conditions={"hour": int(avg_hour), "hour_tolerance": 2},
                    typical_action=actions[0].get("action", {}),
                    occurrence_count=len(actions),
                    confidence=self._calculate_confidence(len(actions), hour_stddev),
                )
            else:
                # Update existing pattern
                pattern = self._patterns[pattern_id]
                pattern.occurrence_count += len(actions)
                pattern.last_triggered = datetime.now(timezone.utc).isoformat()
                pattern.updated_at = pattern.last_triggered
                pattern.confidence = self._calculate_confidence(pattern.occurrence_count, hour_stddev)
    
    def _detect_presence_pattern(self, entity_id: str, actions: List[Dict[str, Any]]) -> None:
        """Detect presence-based patterns."""
        # Check if actions correlate with presence events
        presence_correlated = sum(1 for a in actions if a.get("context", {}).get("presence_detected"))
        
        if presence_correlated >= self._min_occurrences_for_pattern:
            pattern_id = f"presence_pattern_{entity_id}"
            
            if pattern_id not in self._patterns:
                self._pattern_counter += 1
                self._patterns[pattern_id] = BehavioralPattern(
                    pattern_id=pattern_id,
                    pattern_type=PatternType.PRESENCE_BASED,
                    zone_id=actions[0].get("zone_id", "unknown"),
                    module_id=actions[0].get("module_id", "unknown"),
                    entity_id=entity_id,
                    trigger_conditions={"presence_detected": True},
                    typical_action=actions[0].get("action", {}),
                    occurrence_count=presence_correlated,
                    confidence=self._calculate_confidence(presence_correlated, 0.5),
                )

    def _detect_calendar_pattern(self, entity_id: str, actions: List[Dict[str, Any]]) -> None:
        """Detect calendar-correlated patterns."""
        calendar_actions = [
            action for action in actions
            if action.get("context", {}).get("calendar_summary")
            or action.get("context", {}).get("calendar_event")
            or action.get("context", {}).get("away_events")
        ]

        if len(calendar_actions) < self._min_occurrences_for_pattern:
            return

        first_context = calendar_actions[0].get("context", {})
        summary = str(
            first_context.get("calendar_summary")
            or first_context.get("calendar_event")
            or "calendar_event"
        ).strip()
        pattern_id = f"calendar_pattern_{entity_id}_{summary.lower().replace(' ', '_')[:24]}"

        if pattern_id not in self._patterns:
            self._pattern_counter += 1
            self._patterns[pattern_id] = BehavioralPattern(
                pattern_id=pattern_id,
                pattern_type=PatternType.CALENDAR_BASED,
                zone_id=calendar_actions[0].get("zone_id", "unknown"),
                module_id=calendar_actions[0].get("module_id", "unknown"),
                entity_id=entity_id,
                trigger_conditions={
                    "calendar_summary": summary,
                    "away_events": bool(first_context.get("away_events")),
                },
                typical_action=calendar_actions[0].get("action", {}),
                occurrence_count=len(calendar_actions),
                confidence=self._calculate_confidence(len(calendar_actions), 0.5),
            )
    
    def _calculate_confidence(self, occurrence_count: int, stddev: float) -> PredictionConfidence:
        """Calculate confidence level from pattern statistics."""
        # Base confidence from occurrence count
        count_score = min(occurrence_count / 10.0, 1.0)  # Max at 10 occurrences
        
        # Adjust for stddev (lower is better)
        stddev_score = max(0, 1.0 - (stddev / 5.0))
        
        # Combined score
        combined_score = (count_score + stddev_score) / 2.0
        
        if combined_score >= 0.8:
            return PredictionConfidence.VERY_HIGH
        elif combined_score >= 0.6:
            return PredictionConfidence.HIGH
        elif combined_score >= 0.4:
            return PredictionConfidence.MEDIUM
        elif combined_score >= 0.2:
            return PredictionConfidence.LOW
        else:
            return PredictionConfidence.VERY_LOW
    
    def generate_predictions(self, context: Optional[Dict[str, Any]] = None) -> List[PredictiveProposal]:
        """Generate predictive proposals based on patterns and current context."""
        predictions = []
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        current_day = now.strftime("%a").lower()
        
        for pattern in self._patterns.values():
            # Check if pattern matches current context
            match_score = self._evaluate_pattern_match(pattern, context)
            
            if match_score >= self._min_confidence_for_proposal:
                self._proposal_counter += 1
                
                # Create predictive proposal
                proposal = PredictiveProposal(
                    proposal_id=f"pred_{self._proposal_counter}",
                    pattern_id=pattern.pattern_id,
                    zone_id=pattern.zone_id,
                    module_id=pattern.module_id,
                    description=self._generate_prediction_description(pattern, context),
                    predicted_action=pattern.typical_action,
                    confidence=pattern.confidence,
                    confidence_score=match_score,
                    reasoning=self._generate_reasoning(pattern, context),
                    expires_at=(now + timedelta(hours=1)).isoformat(),
                    source_signals=self._derive_source_signals(pattern, context),
                    evidence=self._build_evidence(pattern, context),
                )
                
                predictions.append(proposal)
                self._proposals[proposal.proposal_id] = proposal
        
        # Sort by confidence score
        predictions.sort(key=lambda p: p.confidence_score, reverse=True)
        
        return predictions
    
    def _evaluate_pattern_match(self, pattern: BehavioralPattern, context: Optional[Dict[str, Any]]) -> float:
        """Evaluate how well a pattern matches current context."""
        match_score = 0.0
        factors = 0
        
        # Time-based pattern matching
        if pattern.pattern_type == PatternType.TIME_BASED:
            factors += 1
            trigger_hour = pattern.trigger_conditions.get("hour", 0)
            tolerance = pattern.trigger_conditions.get("hour_tolerance", 2)
            
            current_hour = datetime.now(timezone.utc).hour
            
            # Check if current hour is within tolerance
            hour_diff = abs(current_hour - trigger_hour)
            if hour_diff <= tolerance:
                match_score += 1.0
            elif hour_diff <= tolerance + 1:
                match_score += 0.5
        
        # Presence-based pattern matching
        if pattern.pattern_type == PatternType.PRESENCE_BASED:
            factors += 1
            if context and context.get("presence_detected"):
                match_score += 1.0

        if pattern.pattern_type == PatternType.CALENDAR_BASED:
            factors += 1
            context = context or {}
            expected_summary = str(pattern.trigger_conditions.get("calendar_summary") or "").lower()
            current_summary = str(
                context.get("calendar_summary")
                or context.get("calendar_event")
                or ""
            ).lower()
            away_events = context.get("away_events") or []

            if expected_summary and expected_summary in current_summary:
                match_score += 1.0
            elif away_events:
                match_score += 0.7
        
        # Base confidence from pattern occurrence count
        occurrence_bonus = min(pattern.occurrence_count / 10.0, 0.5)
        match_score += occurrence_bonus
        
        # Normalize
        if factors > 0:
            match_score = min(match_score / factors + 0.3, 1.0)
        
        return match_score
    
    def _generate_prediction_description(self, pattern: BehavioralPattern, context: Optional[Dict[str, Any]]) -> str:
        """Generate human-readable prediction description."""
        if pattern.pattern_type == PatternType.TIME_BASED:
            hour = pattern.trigger_conditions.get("hour", 0)
            return f"Based on your routine, you typically activate this around {hour}:00"
        elif pattern.pattern_type == PatternType.PRESENCE_BASED:
            return "Based on your presence, you typically activate this when arriving"
        elif pattern.pattern_type == PatternType.CALENDAR_BASED:
            summary = pattern.trigger_conditions.get("calendar_summary") or "calendar activity"
            return f"Based on your calendar, this usually happens around {summary}"
        else:
            return "Based on your behavior patterns, this action is likely needed"
    
    def _generate_reasoning(self, pattern: BehavioralPattern, context: Optional[Dict[str, Any]]) -> str:
        """Generate reasoning for prediction."""
        reasons = []
        
        if pattern.occurrence_count >= 5:
            reasons.append(f"Observed {pattern.occurrence_count} times")
        
        if pattern.pattern_type == PatternType.TIME_BASED:
            reasons.append("Time-based pattern detected")
        elif pattern.pattern_type == PatternType.PRESENCE_BASED:
            reasons.append("Presence-correlated pattern detected")
        elif pattern.pattern_type == PatternType.CALENDAR_BASED:
            reasons.append("Calendar-correlated pattern detected")

        if context and context.get("presence_detected"):
            reasons.append("Presence currently detected")

        if context and (context.get("calendar_summary") or context.get("calendar_event") or context.get("away_events")):
            reasons.append("Calendar context currently active")

        return ". ".join(reasons) if reasons else "Pattern match"

    def _derive_source_signals(self, pattern: BehavioralPattern, context: Optional[Dict[str, Any]]) -> List[str]:
        """Derive source signals for the canonical proposal contract."""
        signals = ["pattern"]
        if pattern.pattern_type == PatternType.PRESENCE_BASED or (context and context.get("presence_detected")):
            signals.append("presence")
        if pattern.pattern_type == PatternType.CALENDAR_BASED or (
            context and (context.get("calendar_summary") or context.get("calendar_event") or context.get("away_events"))
        ):
            signals.append("calendar")
        return signals

    def _build_evidence(self, pattern: BehavioralPattern, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build lightweight evidence payload for proposals."""
        context = context or {}
        return {
            "occurrence_count": pattern.occurrence_count,
            "trigger_conditions": dict(pattern.trigger_conditions),
            "active_context": {
                key: context[key]
                for key in ("presence_detected", "calendar_summary", "calendar_event", "away_events")
                if key in context and context[key] not in (None, "", [])
            },
        }
    
    def get_predictions(self, unresolved_only: bool = True) -> List[Dict[str, Any]]:
        """Get predictive proposals."""
        proposals = list(self._proposals.values())
        
        if unresolved_only:
            proposals = [p for p in proposals if not p.accepted and not p.rejected]
        
        # Sort by confidence score
        proposals.sort(key=lambda p: p.confidence_score, reverse=True)

        return [p.to_dict() for p in proposals]

    def get_proposal(self, proposal_id: str) -> Optional[PredictiveProposal]:
        """Return a single predictive proposal."""
        return self._proposals.get(proposal_id)
    
    def accept_prediction(self, proposal_id: str) -> bool:
        """Accept a predictive proposal."""
        if proposal_id not in self._proposals:
            return False
        
        proposal = self._proposals[proposal_id]
        proposal.accepted = True
        
        # Reinforce the pattern
        if proposal.pattern_id in self._patterns:
            pattern = self._patterns[proposal.pattern_id]
            pattern.occurrence_count += 1
            pattern.last_triggered = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def reject_prediction(self, proposal_id: str, feedback: Optional[str] = None) -> bool:
        """Reject a predictive proposal."""
        if proposal_id not in self._proposals:
            return False
        
        proposal = self._proposals[proposal_id]
        proposal.rejected = True
        proposal.feedback = feedback
        
        # Weaken the pattern
        if proposal.pattern_id in self._patterns:
            pattern = self._patterns[proposal.pattern_id]
            pattern.confidence = self._downgrade_confidence(pattern.confidence)
        
        return True
    
    def _downgrade_confidence(self, confidence: PredictionConfidence) -> PredictionConfidence:
        """Downgrade confidence level."""
        confidence_order = [
            PredictionConfidence.VERY_HIGH,
            PredictionConfidence.HIGH,
            PredictionConfidence.MEDIUM,
            PredictionConfidence.LOW,
            PredictionConfidence.VERY_LOW,
        ]
        
        idx = confidence_order.index(confidence)
        if idx < len(confidence_order) - 1:
            return confidence_order[idx + 1]
        return confidence
    
    def get_patterns(self) -> List[Dict[str, Any]]:
        """Get all recognized patterns."""
        return [p.to_dict() for p in self._patterns.values()]

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate predictive automation stats."""
        proposals = list(self._proposals.values())
        unresolved = [p for p in proposals if not p.accepted and not p.rejected]
        accepted = [p for p in proposals if p.accepted]
        rejected = [p for p in proposals if p.rejected]

        patterns_by_type: Dict[str, int] = {}
        for pattern in self._patterns.values():
            patterns_by_type[pattern.pattern_type.value] = patterns_by_type.get(pattern.pattern_type.value, 0) + 1

        return {
            "patterns_total": len(self._patterns),
            "patterns_by_type": patterns_by_type,
            "proposals_total": len(proposals),
            "proposals_unresolved": len(unresolved),
            "proposals_accepted": len(accepted),
            "proposals_rejected": len(rejected),
            "recent_actions": len(self._recent_actions),
        }


def create_predictive_automation_engine() -> PredictiveAutomationEngine:
    """Factory function to create predictive automation engine."""
    return PredictiveAutomationEngine()
