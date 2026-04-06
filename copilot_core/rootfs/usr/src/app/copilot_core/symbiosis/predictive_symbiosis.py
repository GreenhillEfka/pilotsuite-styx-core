"""Predictive Symbiosis Engine — ML-based Rule Generation.
Analyzes event history and auto-generates optimal rules.
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

_LOGGER = logging.getLogger(__name__)

@dataclass
class PatternCandidate:
    pattern_id: str
    trigger_event: str
    context: dict
    frequency: int
    confidence: float
    suggested_action: dict

class PredictiveSymbiosisEngine:
    def __init__(self, event_history: List[dict] = None):
        self.event_history = event_history or []
        self.patterns: Dict[str, PatternCandidate] = {}
        self._min_frequency = 3
        self._min_confidence = 0.7
    
    def add_event(self, event: dict):
        self.event_history.append({
            **event,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Keep last 1000 events
        if len(self.event_history) > 1000:
            self.event_history = self.event_history[-1000:]
    
    def analyze_patterns(self) -> List[PatternCandidate]:
        """Analyze event history for recurring patterns."""
        _LOGGER.info(f"Analyzing {len(self.event_history)} events for patterns")
        
        # Group events by hour + zone
        hourly_patterns = defaultdict(list)
        for event in self.event_history:
            ts = event.get("timestamp", "")
            zone = event.get("zone_id", "unknown")
            event_type = event.get("event_type", "unknown")
            
            if ts:
                hour = ts[11:13]  # Extract hour from ISO string
                key = f"{zone}_{hour}_{event_type}"
                hourly_patterns[key].append(event)
        
        # Find frequent patterns
        new_patterns = []
        for key, events in hourly_patterns.items():
            if len(events) >= self._min_frequency:
                zone, hour, event_type = key.split("_", 2)
                confidence = min(1.0, len(events) / 10.0)
                
                if confidence >= self._min_confidence:
                    pattern = PatternCandidate(
                        pattern_id=f"pattern_{key}",
                        trigger_event=event_type,
                        context={"zone_id": zone, "hour": hour},
                        frequency=len(events),
                        confidence=confidence,
                        suggested_action=self._infer_action(events)
                    )
                    new_patterns.append(pattern)
                    self.patterns[pattern.pattern_id] = pattern
        
        _LOGGER.info(f"Found {len(new_patterns)} new patterns")
        return new_patterns
    
    def _infer_action(self, events: List[dict]) -> dict:
        """Infer the most likely action from event cluster."""
        # Simple heuristic: if presence events cluster, suggest context change
        event_types = [e.get("event_type") for e in events]
        
        if event_types.count("presence") > len(event_types) * 0.7:
            return {"type": "context_change", "context": "occupied"}
        elif event_types.count("motion") > len(event_types) * 0.5:
            return {"type": "ha_service", "service": "light.turn_on"}
        else:
            return {"type": "log", "message": "pattern_detected"}
    
    def get_suggested_rules(self) -> List[dict]:
        """Convert patterns to rule suggestions."""
        rules = []
        for pattern in self.patterns.values():
            rule = {
                "pattern_id": pattern.pattern_id,
                "condition": {
                    "logic": "AND",
                    "checks": [
                        {"type": pattern.trigger_event},
                        {"type": "time_hour", "value": pattern.context.get("hour")}
                    ]
                },
                "action": pattern.suggested_action,
                "confidence": pattern.confidence,
                "frequency": pattern.frequency
            }
            rules.append(rule)
        return rules
    
    def get_pattern_stats(self) -> dict:
        return {
            "total_events": len(self.event_history),
            "total_patterns": len(self.patterns),
            "high_confidence_patterns": sum(1 for p in self.patterns.values() if p.confidence > 0.8),
            "patterns_by_zone": self._count_by_field("zone_id"),
            "patterns_by_hour": self._count_by_field("hour")
        }
    
    def _count_by_field(self, field: str) -> dict:
        counts = defaultdict(int)
        for pattern in self.patterns.values():
            key = pattern.context.get(field, "unknown")
            counts[key] += 1
        return dict(counts)
