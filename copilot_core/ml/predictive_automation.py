"""P3-003: Predictive Automation — Auto-Rule-Generation, Suggestions."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class AutomationConfidence(Enum):
    """Confidence levels for automation suggestions."""
    LOW = "low"  # <50% - Don't suggest
    MEDIUM = "medium"  # 50-75% - Suggest with confirmation
    HIGH = "high"  # 75-90% - Suggest with opt-out
    VERY_HIGH = "very_high"  # >90% - Auto-apply


@dataclass
class AutomationRule:
    """An automation rule."""
    id: str
    name: str
    trigger: str
    conditions: Dict[str, Any]
    action: str
    action_params: Dict[str, Any]
    confidence: AutomationConfidence
    success_rate: float = 0.0
    executions: int = 0
    created_at: float = field(default_factory=time.time)
    last_triggered: float = 0.0


@dataclass
class AutomationSuggestion:
    """A suggested automation rule."""
    description: str
    trigger: str
    action: str
    confidence: float
    expected_benefit: str
    example_context: Dict[str, Any]


class PredictiveAutomationEngine:
    """Generates automation rules from patterns."""

    def __init__(self):
        self._rules: Dict[str, AutomationRule] = {}
        self._suggestions: List[AutomationSuggestion] = []
        self._execution_history: List[Dict[str, Any]] = []
        self._pattern_callback: Optional[Callable] = None

    def set_pattern_callback(self, callback: Callable):
        """Set callback to fetch patterns from pattern engine."""
        self._pattern_callback = callback

    def generate_rules_from_patterns(self) -> List[AutomationRule]:
        """Generate automation rules from detected patterns."""
        if not self._pattern_callback:
            return []
        
        patterns = self._pattern_callback()
        new_rules = []
        
        for pattern in patterns:
            if pattern.confidence < 0.7:
                continue
            
            # Generate rule from pattern
            rule = self._pattern_to_rule(pattern)
            if rule:
                self._rules[rule.id] = rule
                new_rules.append(rule)
                logger.info(f"Generated automation rule: {rule.name}")
        
        return new_rules

    def _pattern_to_rule(self, pattern) -> Optional[AutomationRule]:
        """Convert a pattern to automation rule."""
        import hashlib
        
        rule_id = hashlib.sha256(f"rule_{pattern.id}_{time.time()}".encode()).hexdigest()[:16]
        
        # Determine confidence level
        if pattern.confidence < 0.5:
            confidence = AutomationConfidence.LOW
        elif pattern.confidence < 0.75:
            confidence = AutomationConfidence.MEDIUM
        elif pattern.confidence < 0.9:
            confidence = AutomationConfidence.HIGH
        else:
            confidence = AutomationConfidence.VERY_HIGH
        
        # Skip low confidence
        if confidence == AutomationConfidence.LOW:
            return None
        
        # Generate rule based on pattern type
        trigger = f"pattern:{pattern.pattern_type.value}"
        action = f"suggest:{pattern.id}"
        
        rule = AutomationRule(
            id=rule_id,
            name=f"Auto: {pattern.description[:50]}",
            trigger=trigger,
            conditions={"pattern_id": pattern.id},
            action=action,
            action_params={"pattern_confidence": pattern.confidence},
            confidence=confidence,
        )
        
        return rule

    def execute_rule(self, rule_id: str, context: Dict[str, Any]) -> bool:
        """Execute an automation rule."""
        if rule_id not in self._rules:
            return False
        
        rule = self._rules[rule_id]
        rule.executions += 1
        rule.last_triggered = time.time()
        
        # Log execution
        self._execution_history.append({
            "rule_id": rule_id,
            "timestamp": time.time(),
            "context": context,
            "success": True  # Would track actual success
        })
        
        # Update success rate
        recent = [e for e in self._execution_history if e["rule_id"] == rule_id][-100:]
        successes = sum(1 for e in recent if e.get("success", False))
        rule.success_rate = successes / max(1, len(recent))
        
        logger.debug(f"Executed rule: {rule.name}")
        return True

    def get_suggestions(self, context: Dict[str, Any]) -> List[AutomationSuggestion]:
        """Get automation suggestions for current context."""
        suggestions = []
        
        # Analyze patterns for potential automations
        if self._pattern_callback:
            patterns = self._pattern_callback()
            for pattern in patterns:
                if pattern.confidence > 0.6:
                    suggestion = AutomationSuggestion(
                        description=f"Automate: {pattern.description}",
                        trigger=f"When {pattern.pattern_type.value} pattern detected",
                        action=f"Execute related action automatically",
                        confidence=pattern.confidence,
                        expected_benefit=f"Save time on repetitive task (detected {pattern.frequency:.1f}x/period)",
                        example_context=pattern.metadata
                    )
                    suggestions.append(suggestion)
        
        return suggestions[:5]

    def accept_suggestion(self, suggestion: AutomationSuggestion) -> AutomationRule:
        """Accept a suggestion and create a rule."""
        import hashlib
        
        rule_id = hashlib.sha256(f"suggestion_{time.time()}".encode()).hexdigest()[:16]
        
        rule = AutomationRule(
            id=rule_id,
            name=suggestion.description[:50],
            trigger=suggestion.trigger,
            conditions={},
            action=suggestion.action,
            action_params={},
            confidence=AutomationConfidence.HIGH if suggestion.confidence > 0.8 else AutomationConfidence.MEDIUM,
        )
        
        self._rules[rule_id] = rule
        return rule

    def get_rules(self) -> List[AutomationRule]:
        """Get all automation rules."""
        return list(self._rules.values())

    def delete_rule(self, rule_id: str) -> bool:
        """Delete an automation rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get automation statistics."""
        return {
            "total_rules": len(self._rules),
            "total_executions": sum(r.executions for r in self._rules.values()),
            "avg_success_rate": sum(r.success_rate for r in self._rules.values()) / max(1, len(self._rules)),
            "pending_suggestions": len(self._suggestions),
        }


# Global default automation engine
default_automation_engine: Optional[PredictiveAutomationEngine] = None


def init_automation_engine() -> PredictiveAutomationEngine:
    """Initialize global automation engine."""
    global default_automation_engine
    default_automation_engine = PredictiveAutomationEngine()
    return default_automation_engine
