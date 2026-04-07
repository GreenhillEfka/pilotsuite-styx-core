"""Rules Engine — Slice 30.

Rules engine for PilotSuite Core automation.

Features:
- Rule definition and evaluation
- Complex condition expressions
- Rule chaining and dependencies
- Conflict detection
- Priority-based execution
- Rule analytics
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class RuleOperator(Enum):
    """Rule condition operators."""
    EQ = "eq"  # Equal
    NE = "ne"  # Not equal
    GT = "gt"  # Greater than
    GTE = "gte"  # Greater than or equal
    LT = "lt"  # Less than
    LTE = "lte"  # Less than or equal
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # Regex match
    IN = "in"  # In list
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class RuleLogical(Enum):
    """Logical operators for combining conditions."""
    AND = "and"
    OR = "or"
    NOT = "not"


class RuleStatus(Enum):
    """Rule execution status."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class RuleCondition:
    """Single rule condition."""
    field: str
    operator: RuleOperator
    value: Any
    negate: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
            "negate": self.negate,
        }


@dataclass
class RuleAction:
    """Rule action definition."""
    action_id: str
    action_type: str
    parameters: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "parameters": self.parameters,
        }


@dataclass
class Rule:
    """Rule definition."""
    rule_id: str
    name: str
    description: str
    conditions: List[RuleCondition]
    logical_operator: RuleLogical = RuleLogical.AND
    actions: List[RuleAction] = field(default_factory=list)
    priority: int = 0
    status: RuleStatus = RuleStatus.ENABLED
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_triggered: Optional[str] = None
    trigger_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "conditions": [c.to_dict() for c in self.conditions],
            "logical_operator": self.logical_operator.value,
            "actions": [a.to_dict() for a in self.actions],
            "priority": self.priority,
            "status": self.status.value,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }


@dataclass
class RuleEvaluationResult:
    """Result of rule evaluation."""
    rule_id: str
    matched: bool
    conditions_evaluated: int
    conditions_matched: int
    actions_executed: int
    actions_failed: int
    evaluation_time_ms: int
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "matched": self.matched,
            "conditions_evaluated": self.conditions_evaluated,
            "conditions_matched": self.conditions_matched,
            "actions_executed": self.actions_executed,
            "actions_failed": self.actions_failed,
            "evaluation_time_ms": self.evaluation_time_ms,
            "error_message": self.error_message,
        }


class RulesEngine:
    """Rules engine for automation."""
    
    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._action_handlers: Dict[str, Callable] = {}
        self._evaluation_log: List[RuleEvaluationResult] = []
        self._max_log_size = 1000
        
        # Register built-in action handlers
        self._register_builtin_actions()
    
    def _register_builtin_actions(self) -> None:
        """Register built-in action handlers."""
        self._action_handlers["log"] = self._action_log
        self._action_handlers["set_variable"] = self._action_set_variable
        self._action_handlers["notify"] = self._action_notify
    
    def _action_log(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Log action handler."""
        message = kwargs.get("message", "")
        level = kwargs.get("level", "info")
        
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)
        
        return {"logged": message}
    
    def _action_set_variable(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Set variable action handler."""
        name = kwargs.get("name", "")
        value = kwargs.get("value")
        
        context[name] = value
        
        return {"variable_set": name, "value": value}
    
    def _action_notify(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Notify action handler."""
        title = kwargs.get("title", "")
        message = kwargs.get("message", "")
        
        logger.info("Notification: %s - %s", title, message)
        
        return {"notification": {"title": title, "message": message}}
    
    def register_action(self, action_type: str, handler: Callable) -> None:
        """Register a custom action handler."""
        self._action_handlers[action_type] = handler
        logger.info("Action handler registered: %s", action_type)
    
    def create_rule(self, name: str, description: str,
                   conditions: List[Dict[str, Any]],
                   actions: List[Dict[str, Any]],
                   logical_operator: str = "and",
                   priority: int = 0,
                   tags: Optional[List[str]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new rule."""
        import uuid
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"
        
        # Parse conditions
        parsed_conditions = []
        for cond in conditions:
            condition = RuleCondition(
                field=cond.get("field", ""),
                operator=RuleOperator(cond.get("operator", "eq")),
                value=cond.get("value"),
                negate=cond.get("negate", False),
            )
            parsed_conditions.append(condition)
        
        # Parse actions
        parsed_actions = []
        for act in actions:
            action = RuleAction(
                action_id=act.get("action_id", f"action_{uuid.uuid4().hex[:8]}"),
                action_type=act.get("action_type", "log"),
                parameters=act.get("parameters", {}),
            )
            parsed_actions.append(action)
        
        rule = Rule(
            rule_id=rule_id,
            name=name,
            description=description,
            conditions=parsed_conditions,
            logical_operator=RuleLogical(logical_operator),
            actions=parsed_actions,
            priority=priority,
            tags=tags or [],
            metadata=metadata or {},
        )
        
        self._rules[rule_id] = rule
        
        logger.info("Rule created: %s (%s)", name, rule_id)
        
        return rule_id
    
    def evaluate_rule(self, rule_id: str, context: Dict[str, Any]) -> RuleEvaluationResult:
        """Evaluate a single rule."""
        import time
        start_time = time.time()
        
        if rule_id not in self._rules:
            return RuleEvaluationResult(
                rule_id=rule_id,
                matched=False,
                conditions_evaluated=0,
                conditions_matched=0,
                actions_executed=0,
                actions_failed=0,
                evaluation_time_ms=0,
                error_message="Rule not found",
            )
        
        rule = self._rules[rule_id]
        
        if rule.status != RuleStatus.ENABLED:
            return RuleEvaluationResult(
                rule_id=rule_id,
                matched=False,
                conditions_evaluated=0,
                conditions_matched=0,
                actions_executed=0,
                actions_failed=0,
                evaluation_time_ms=0,
                error_message="Rule disabled",
            )
        
        # Evaluate conditions
        conditions_matched = 0
        conditions_evaluated = len(rule.conditions)
        
        for condition in rule.conditions:
            if self._evaluate_condition(condition, context):
                conditions_matched += 1
        
        # Determine if rule matches based on logical operator
        if rule.logical_operator == RuleLogical.AND:
            matched = conditions_matched == conditions_evaluated
        elif rule.logical_operator == RuleLogical.OR:
            matched = conditions_matched > 0
        elif rule.logical_operator == RuleLogical.NOT:
            matched = conditions_matched == 0
        else:
            matched = False
        
        # Execute actions if matched
        actions_executed = 0
        actions_failed = 0
        
        if matched:
            for action in rule.actions:
                try:
                    if action.action_type in self._action_handlers:
                        self._action_handlers[action.action_type](
                            context, **action.parameters
                        )
                        actions_executed += 1
                    else:
                        logger.warning("Unknown action type: %s", action.action_type)
                        actions_failed += 1
                except Exception as exc:
                    logger.exception("Action %s failed: %s", action.action_id, exc)
                    actions_failed += 1
            
            # Update rule stats
            rule.trigger_count += 1
            rule.last_triggered = datetime.now(timezone.utc).isoformat()
        
        evaluation_time_ms = int((time.time() - start_time) * 1000)
        
        result = RuleEvaluationResult(
            rule_id=rule_id,
            matched=matched,
            conditions_evaluated=conditions_evaluated,
            conditions_matched=conditions_matched,
            actions_executed=actions_executed,
            actions_failed=actions_failed,
            evaluation_time_ms=evaluation_time_ms,
        )
        
        # Log evaluation
        self._evaluation_log.append(result)
        if len(self._evaluation_log) > self._max_log_size:
            self._evaluation_log = self._evaluation_log[-self._max_log_size:]
        
        return result
    
    def _evaluate_condition(self, condition: RuleCondition,
                           context: Dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        # Get field value from context
        value = self._get_field_value(condition.field, context)
        
        # Handle EXISTS/NOT_EXISTS operators
        if condition.operator == RuleOperator.EXISTS:
            result = value is not None
        elif condition.operator == RuleOperator.NOT_EXISTS:
            result = value is None
        else:
            # Compare values
            result = self._compare_values(value, condition.operator, condition.value)
        
        # Apply negation
        if condition.negate:
            result = not result
        
        return result
    
    def _get_field_value(self, field: str, context: Dict[str, Any]) -> Any:
        """Get field value from context (supports dot notation)."""
        parts = field.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        
        return value
    
    def _compare_values(self, actual: Any, operator: RuleOperator,
                       expected: Any) -> bool:
        """Compare values based on operator."""
        try:
            if operator == RuleOperator.EQ:
                return actual == expected
            elif operator == RuleOperator.NE:
                return actual != expected
            elif operator == RuleOperator.GT:
                return float(actual) > float(expected)
            elif operator == RuleOperator.GTE:
                return float(actual) >= float(expected)
            elif operator == RuleOperator.LT:
                return float(actual) < float(expected)
            elif operator == RuleOperator.LTE:
                return float(actual) <= float(expected)
            elif operator == RuleOperator.CONTAINS:
                return str(expected) in str(actual)
            elif operator == RuleOperator.STARTS_WITH:
                return str(actual).startswith(str(expected))
            elif operator == RuleOperator.ENDS_WITH:
                return str(actual).endswith(str(expected))
            elif operator == RuleOperator.MATCHES:
                return bool(re.search(str(expected), str(actual)))
            elif operator == RuleOperator.IN:
                return actual in expected
            elif operator == RuleOperator.NOT_IN:
                return actual not in expected
            else:
                return False
        except (ValueError, TypeError):
            return False
    
    def evaluate_all_rules(self, context: Dict[str, Any]) -> List[RuleEvaluationResult]:
        """Evaluate all enabled rules."""
        # Sort by priority (higher first)
        sorted_rules = sorted(
            [r for r in self._rules.values() if r.status == RuleStatus.ENABLED],
            key=lambda r: r.priority,
            reverse=True,
        )
        
        results = []
        for rule in sorted_rules:
            result = self.evaluate_rule(rule.rule_id, context)
            results.append(result)
        
        return results
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        if rule_id not in self._rules:
            return False
        
        self._rules[rule_id].status = RuleStatus.ENABLED
        return True
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        if rule_id not in self._rules:
            return False
        
        self._rules[rule_id].status = RuleStatus.DISABLED
        return True
    
    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get rule details."""
        if rule_id not in self._rules:
            return None
        
        return self._rules[rule_id].to_dict()
    
    def get_all_rules(self, status: Optional[RuleStatus] = None,
                     tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all rules with optional filters."""
        rules = list(self._rules.values())
        
        if status:
            rules = [r for r in rules if r.status == status]
        
        if tags:
            rules = [r for r in rules if any(t in r.tags for t in tags)]
        
        # Sort by priority (higher first)
        rules.sort(key=lambda r: r.priority, reverse=True)
        
        return [r.to_dict() for r in rules]
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule."""
        if rule_id not in self._rules:
            return False
        
        del self._rules[rule_id]
        return True
    
    def get_evaluation_log(self, rule_id: Optional[str] = None,
                          matched_only: bool = False,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get evaluation log."""
        logs = self._evaluation_log
        
        if rule_id:
            logs = [l for l in logs if l.rule_id == rule_id]
        
        if matched_only:
            logs = [l for l in logs if l.matched]
        
        # Sort by evaluation time (newest first - assuming log is in order)
        logs = logs[-limit:]
        logs.reverse()
        
        return [l.to_dict() for l in logs]
    
    def get_rule_statistics(self, rule_id: str) -> Dict[str, Any]:
        """Get statistics for a rule."""
        if rule_id not in self._rules:
            return {}
        
        rule = self._rules[rule_id]
        
        # Count evaluations from log
        evaluations = [l for l in self._evaluation_log if l.rule_id == rule_id]
        matched_count = len([l for l in evaluations if l.matched])
        
        avg_eval_time = (
            sum(l.evaluation_time_ms for l in evaluations) / len(evaluations)
            if evaluations else 0
        )
        
        return {
            "rule_id": rule_id,
            "trigger_count": rule.trigger_count,
            "evaluations_total": len(evaluations),
            "evaluations_matched": matched_count,
            "match_rate": matched_count / len(evaluations) if evaluations else 0,
            "avg_evaluation_time_ms": round(avg_eval_time, 2),
            "last_triggered": rule.last_triggered,
        }
    
    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """Detect potential rule conflicts."""
        conflicts = []
        
        enabled_rules = [
            r for r in self._rules.values()
            if r.status == RuleStatus.ENABLED
        ]
        
        # Check for rules with same conditions but different actions
        for i, rule1 in enumerate(enabled_rules):
            for rule2 in enabled_rules[i+1:]:
                # Simple conflict detection: same conditions
                if self._conditions_equal(rule1.conditions, rule2.conditions):
                    conflicts.append({
                        "type": "duplicate_conditions",
                        "rule1_id": rule1.rule_id,
                        "rule2_id": rule2.rule_id,
                        "description": f"Rules '{rule1.name}' and '{rule2.name}' have identical conditions",
                    })
        
        return conflicts
    
    def _conditions_equal(self, conditions1: List[RuleCondition],
                         conditions2: List[RuleCondition]) -> bool:
        """Check if two condition lists are equivalent."""
        if len(conditions1) != len(conditions2):
            return False
        
        for c1, c2 in zip(conditions1, conditions2):
            if (c1.field != c2.field or
                c1.operator != c2.operator or
                c1.value != c2.value or
                c1.negate != c2.negate):
                return False
        
        return True
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """Get rules engine summary."""
        total_rules = len(self._rules)
        enabled_rules = len([r for r in self._rules.values() if r.status == RuleStatus.ENABLED])
        disabled_rules = len([r for r in self._rules.values() if r.status == RuleStatus.DISABLED])
        
        total_triggers = sum(r.trigger_count for r in self._rules.values())
        
        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": disabled_rules,
            "total_triggers": total_triggers,
            "registered_actions": len(self._action_handlers),
        }


def create_rules_engine() -> RulesEngine:
    """Factory function to create rules engine."""
    return RulesEngine()
