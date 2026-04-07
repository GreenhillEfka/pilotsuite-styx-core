"""P3-001: Pattern Detection Engine — Temporal Patterns, Frequency Analysis."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Types of detected patterns."""
    DAILY = "daily"  # Repeats every day
    WEEKLY = "weekly"  # Repeats every week
    MONTHLY = "monthly"  # Repeats every month
    EVENT_TRIGGERED = "event_triggered"  # Triggered by specific event
    SEASONAL = "seasonal"  # Seasonal variation


@dataclass
class DetectedPattern:
    """A detected pattern in user behavior."""
    id: str
    pattern_type: PatternType
    description: str
    confidence: float  # 0.0 to 1.0
    frequency: float  # Occurrences per period
    examples: List[Dict[str, Any]] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventData:
    """Single event for pattern analysis."""
    timestamp: float
    event_type: str
    entity_id: str
    value: Any
    context: Dict[str, Any] = field(default_factory=dict)


class PatternDetectionEngine:
    """Detects patterns in temporal event data."""

    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
        self._events: List[EventData] = []
        self._patterns: Dict[str, DetectedPattern] = {}
        self._event_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._timestamps: Dict[str, List[float]] = defaultdict(list)

    def add_event(self, event: EventData):
        """Add event for pattern analysis."""
        self._events.append(event)
        
        # Index by type and time
        self._event_counts[event.event_type][self._get_hour_key(event.timestamp)] += 1
        self._event_counts[event.event_type][self._get_day_key(event.timestamp)] += 1
        self._timestamps[event.event_type].append(event.timestamp)
        
        # Detect patterns periodically
        if len(self._events) % 100 == 0:
            self._detect_patterns()

    def _get_hour_key(self, timestamp: float) -> str:
        """Get hour-of-day key."""
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return f"{dt.hour:02d}"

    def _get_day_key(self, timestamp: float) -> str:
        """Get day-of-week key."""
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return f"{dt.weekday()}"

    def _detect_patterns(self):
        """Detect patterns in collected events."""
        for event_type in self._event_counts:
            # Daily patterns
            daily_pattern = self._detect_daily_pattern(event_type)
            if daily_pattern and daily_pattern.confidence >= self.min_confidence:
                self._patterns[f"daily_{event_type}"] = daily_pattern
            
            # Weekly patterns
            weekly_pattern = self._detect_weekly_pattern(event_type)
            if weekly_pattern and weekly_pattern.confidence >= self.min_confidence:
                self._patterns[f"weekly_{event_type}"] = weekly_pattern

    def _detect_daily_pattern(self, event_type: str) -> Optional[DetectedPattern]:
        """Detect daily repeating patterns."""
        hour_counts = self._event_counts[event_type]
        
        if not hour_counts:
            return None
        
        # Find peak hours
        total = sum(hour_counts.values())
        if total < 10:  # Need minimum data
            return None
        
        # Calculate hour distribution
        hour_dist = {h: c / total for h, c in hour_counts.items()}
        
        # Find dominant hours (>20% of events)
        dominant_hours = [h for h, ratio in hour_dist.items() if ratio > 0.2]
        
        if not dominant_hours:
            return None
        
        confidence = max(hour_dist.values()) if hour_dist else 0.0
        
        return DetectedPattern(
            id=f"daily_{event_type}",
            pattern_type=PatternType.DAILY,
            description=f"Events occur primarily at hours: {', '.join(sorted(dominant_hours))}",
            confidence=confidence,
            frequency=len(self._timestamps[event_type]) / max(1, self._get_days_span(event_type)),
            metadata={"dominant_hours": dominant_hours, "distribution": hour_dist}
        )

    def _detect_weekly_pattern(self, event_type: str) -> Optional[DetectedPattern]:
        """Detect weekly repeating patterns."""
        day_counts = {k: v for k, v in self._event_counts[event_type].items() if k.isdigit()}
        
        if not day_counts:
            return None
        
        total = sum(int(v) for v in day_counts.values())
        if total < 10:
            return None
        
        # Find peak days
        day_dist = {d: int(c) / total for d, c in day_counts.items()}
        dominant_days = [d for d, ratio in day_dist.items() if ratio > 0.25]
        
        if not dominant_days:
            return None
        
        confidence = max(day_dist.values()) if day_dist else 0.0
        
        return DetectedPattern(
            id=f"weekly_{event_type}",
            pattern_type=PatternType.WEEKLY,
            description=f"Events occur primarily on days: {', '.join(sorted(dominant_days))}",
            confidence=confidence,
            frequency=len(self._timestamps[event_type]) / max(1, self._get_weeks_span(event_type)),
            metadata={"dominant_days": dominant_days, "distribution": day_dist}
        )

    def _get_days_span(self, event_type: str) -> float:
        """Get time span in days for event type."""
        timestamps = self._timestamps[event_type]
        if len(timestamps) < 2:
            return 1.0
        return (max(timestamps) - min(timestamps)) / (24 * 3600)

    def _get_weeks_span(self, event_type: str) -> float:
        """Get time span in weeks for event type."""
        return self._get_days_span(event_type) / 7.0

    def get_patterns(self, pattern_type: Optional[PatternType] = None) -> List[DetectedPattern]:
        """Get detected patterns."""
        patterns = list(self._patterns.values())
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        return sorted(patterns, key=lambda x: x.confidence, reverse=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics."""
        return {
            "total_events": len(self._events),
            "event_types": len(self._event_counts),
            "patterns_detected": len(self._patterns),
            "high_confidence_patterns": len([p for p in self._patterns.values() if p.confidence > 0.8]),
        }


# Global default pattern engine
default_pattern_engine: Optional[PatternDetectionEngine] = None


def init_pattern_engine(min_confidence: float = 0.6) -> PatternDetectionEngine:
    """Initialize global pattern detection engine."""
    global default_pattern_engine
    default_pattern_engine = PatternDetectionEngine(min_confidence)
    return default_pattern_engine


def record_event(event_type: str, entity_id: str, value: Any, **kwargs):
    """Convenience function to record event."""
    if default_pattern_engine:
        event = EventData(
            timestamp=time.time(),
            event_type=event_type,
            entity_id=entity_id,
            value=value,
            context=kwargs
        )
        default_pattern_engine.add_event(event)


def get_detected_patterns(**kwargs) -> List[DetectedPattern]:
    """Convenience function to get patterns."""
    if default_pattern_engine:
        return default_pattern_engine.get_patterns(**kwargs)
    return []
