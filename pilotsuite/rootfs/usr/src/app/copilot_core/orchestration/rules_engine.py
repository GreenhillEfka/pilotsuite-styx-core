"""Module Orchestration / Rules Engine — Slice 73.

Regelbasierte Automatisierung für Habituszonen.

Features:
- Rule Definitions (IF conditions THEN actions)
- Multi-Module Conditions (Presence, Light, TimeOfDay, Comfort)
- Zone-Specific Rules
- Rule Priorities
- Action Execution
- Rule History & Statistics
- Rule Enable/Disable
- Conflict Resolution
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class RuleOperator(Enum):
    """Rule condition operators."""
    EQ = "eq"  # equals
    NE = "ne"  # not equals
    LT = "lt"  # less than
    LE = "le"  # less or equal
    GT = "gt"  # greater than
    GE = "ge"  # greater or equal
    IN = "in"  # in list
    NOT_IN = "not_in"  # not in list
    BETWEEN = "between"  # between two values


class RuleConnector(Enum):
    """Rule condition connectors."""
    AND = "and"
    OR = "or"


class ActionType(Enum):
    """Action types."""
    LIGHT_TURN_ON = "light.turn_on"
    LIGHT_TURN_OFF = "light.turn_off"
    LIGHT_SCENE = "light.scene"
    LIGHT_DIM = "light.dim"
    NOTIFY = "notify"
    EVENT_EMIT = "event.emit"
    MODULE_CALL = "module.call"
    RULE_ENABLE = "rule.enable"
    RULE_DISABLE = "rule.disable"


class RuleState(Enum):
    """Rule execution state."""
    IDLE = "idle"
    EVALUATING = "evaluating"
    TRIGGERED = "triggered"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class Condition:
    """Single condition in a rule."""
    field: str  # e.g., "presence.state", "light.level", "timeofday.phase"
    operator: RuleOperator
    value: Any
    zone_id: Optional[str] = None  # None = global
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context."""
        actual = self._get_value(context, self.field)
        
        if actual is None:
            return False
        
        if self.operator == RuleOperator.EQ:
            return actual == self.value
        elif self.operator == RuleOperator.NE:
            return actual != self.value
        elif self.operator == RuleOperator.LT:
            return actual < self.value
        elif self.operator == RuleOperator.LE:
            return actual <= self.value
        elif self.operator == RuleOperator.GT:
            return actual > self.value
        elif self.operator == RuleOperator.GE:
            return actual >= self.value
        elif self.operator == RuleOperator.IN:
            return actual in self.value
        elif self.operator == RuleOperator.NOT_IN:
            return actual not in self.value
        elif self.operator == RuleOperator.BETWEEN:
            return self.value[0] <= actual <= self.value[1]
        
        return False
    
    def _get_value(self, context: Dict[str, Any], field: str) -> Any:
        """Get value from context by dot-notation field."""
        parts = field.split(".")
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
            "zone_id": self.zone_id,
        }


@dataclass
class Action:
    """Action to execute when rule triggers."""
    action_type: ActionType
    target_zone: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "target_zone": self.target_zone,
            "parameters": self.parameters,
        }


@dataclass
class Rule:
    """Automation rule."""
    rule_id: str
    name: str
    zone_id: Optional[str]  # None = global rule
    conditions: List[Condition]
    connector: RuleConnector  # AND/OR between conditions
    actions: List[Action]
    priority: int = 50  # 0-100, higher = more important
    enabled: bool = True
    cooldown_seconds: int = 0  # Minimum time between triggers
    description: str = ""
    
    # Runtime state
    state: RuleState = RuleState.IDLE
    last_triggered: Optional[str] = None
    trigger_count: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "zone_id": self.zone_id,
            "conditions": [c.to_dict() for c in self.conditions],
            "connector": self.connector.value,
            "actions": [a.to_dict() for a in self.actions],
            "priority": self.priority,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
            "description": self.description,
            "state": self.state.value,
            "last_triggered": self.last_triggered,
            "trigger_count": self.trigger_count,
        }


@dataclass
class RuleExecution:
    """Rule execution record."""
    execution_id: str
    rule_id: str
    zone_id: Optional[str]
    timestamp: str
    conditions_met: bool
    actions_executed: int
    success: bool
    error: Optional[str] = None
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "rule_id": self.rule_id,
            "zone_id": self.zone_id,
            "timestamp": self.timestamp,
            "conditions_met": self.conditions_met,
            "actions_executed": self.actions_executed,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ModuleConnection:
    """Connection between modules."""
    source_module: str  # e.g., "presence"
    source_field: str  # e.g., "state"
    target_module: str  # e.g., "light"
    target_field: str  # e.g., "auto_enabled"
    transform: Optional[str] = None  # Optional transform function
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_module": self.source_module,
            "source_field": self.source_field,
            "target_module": self.target_module,
            "target_field": self.target_field,
            "transform": self.transform,
        }


class RulesEngine:
    """Rules engine for module orchestration.
    
    Architecture:
        Module States → Context Builder → Rule Evaluation → Action Execution
    
    Usage:
        engine = RulesEngine()
        engine.register_module("presence", presence_module)
        engine.register_module("light", light_module)
        engine.add_rule(rule)
        engine.evaluate_all()
    """
    
    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._modules: Dict[str, Any] = {}  # module_name -> module_instance
        self._module_contexts: Dict[str, Dict[str, Any]] = {}  # module_name -> context
        self._executions: List[RuleExecution] = []
        self._zone_contexts: Dict[str, Dict[str, Any]] = {}  # zone_id -> combined context
        self._action_callbacks: Dict[ActionType, Callable] = {}
        self._connections: List[ModuleConnection] = []
        
        logger.info("RulesEngine initialized")
    
    def register_module(self, name: str, module: Any) -> bool:
        """Register a module with the engine."""
        with self._lock():
            self._modules[name] = module
            self._module_contexts[name] = {}
        
        logger.info("Module registered: %s", name)
        return True
    
    def unregister_module(self, name: str) -> bool:
        """Unregister a module."""
        if name not in self._modules:
            return False
        
        with self._lock():
            del self._modules[name]
            del self._module_contexts[name]
        
        return True
    
    def add_rule(self, rule: Rule) -> str:
        """Add a rule to the engine."""
        with self._lock():
            self._rules[rule.rule_id] = rule
        
        logger.info("Rule added: %s (%s)", rule.rule_id, rule.name)
        return rule.rule_id
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule."""
        if rule_id not in self._rules:
            return False
        
        with self._lock():
            del self._rules[rule_id]
        
        return True
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        if rule_id not in self._rules:
            return False
        
        with self._lock():
            self._rules[rule_id].enabled = True
            self._rules[rule_id].state = RuleState.IDLE
        
        return True
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        if rule_id not in self._rules:
            return False
        
        with self._lock():
            self._rules[rule_id].enabled = False
            self._rules[rule_id].state = RuleState.DISABLED
        
        return True
    
    def register_action_callback(self, action_type: ActionType,
                                callback: Callable) -> None:
        """Register callback for action execution."""
        self._action_callbacks[action_type] = callback
    
    def add_module_connection(self, connection: ModuleConnection) -> None:
        """Add connection between modules."""
        self._connections.append(connection)
    
    def update_module_context(self, module_name: str,
                             context: Dict[str, Any]) -> None:
        """Update context for a module."""
        if module_name not in self._module_contexts:
            self._module_contexts[module_name] = {}
        
        self._module_contexts[module_name].update(context)
    
    def _build_zone_context(self, zone_id: Optional[str]) -> Dict[str, Any]:
        """Build combined context for evaluation."""
        context = {}
        
        # Merge all module contexts
        for module_name, module_context in self._module_contexts.items():
            context[module_name] = module_context
        
        # Add zone-specific data
        if zone_id:
            context["zone_id"] = zone_id
        
        # Add timestamp
        context["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        return context
    
    def evaluate_rule(self, rule: Rule, context: Dict[str, Any]) -> bool:
        """Evaluate a single rule."""
        if not rule.enabled:
            return False
        
        # Check cooldown
        if rule.cooldown_seconds > 0 and rule.last_triggered:
            last = datetime.fromisoformat(rule.last_triggered.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            
            if elapsed < rule.cooldown_seconds:
                return False
        
        # Evaluate conditions
        condition_results = []
        
        for condition in rule.conditions:
            result = condition.evaluate(context)
            condition_results.append(result)
        
        # Combine results
        if rule.connector == RuleConnector.AND:
            all_met = all(condition_results)
        else:  # OR
            all_met = any(condition_results)
        
        return all_met
    
    def execute_actions(self, rule: Rule, context: Dict[str, Any]) -> int:
        """Execute actions for a triggered rule."""
        executed = 0
        
        for action in rule.actions:
            try:
                callback = self._action_callbacks.get(action.action_type)
                
                if callback:
                    callback(action, context)
                    executed += 1
                else:
                    logger.warning("No callback for action type: %s", action.action_type)
            except Exception as e:
                logger.exception("Action execution failed: %s", e)
                rule.last_error = str(e)
        
        return executed
    
    def evaluate_all(self, zone_id: Optional[str] = None) -> List[RuleExecution]:
        """Evaluate all rules."""
        executions = []
        
        # Build context
        context = self._build_zone_context(zone_id)
        
        # Sort rules by priority (higher first)
        sorted_rules = sorted(
            self._rules.values(),
            key=lambda r: r.priority,
            reverse=True,
        )
        
        for rule in sorted_rules:
            # Skip rules for different zones
            if rule.zone_id and rule.zone_id != zone_id:
                continue
            
            execution_id = f"rex_{uuid.uuid4().hex[:16]}"
            
            try:
                rule.state = RuleState.EVALUATING
                
                triggered = self.evaluate_rule(rule, context)
                
                if triggered:
                    rule.state = RuleState.TRIGGERED
                    rule.last_triggered = datetime.now(timezone.utc).isoformat()
                    rule.trigger_count += 1
                    
                    rule.state = RuleState.EXECUTING
                    executed = self.execute_actions(rule, context)
                    
                    rule.state = RuleState.COMPLETED
                    
                    execution = RuleExecution(
                        execution_id=execution_id,
                        rule_id=rule.rule_id,
                        zone_id=zone_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        conditions_met=True,
                        actions_executed=executed,
                        success=True,
                        context_snapshot=context.copy(),
                    )
                else:
                    rule.state = RuleState.IDLE
                    
                    execution = RuleExecution(
                        execution_id=execution_id,
                        rule_id=rule.rule_id,
                        zone_id=zone_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        conditions_met=False,
                        actions_executed=0,
                        success=True,
                    )
                
            except Exception as e:
                rule.state = RuleState.FAILED
                rule.last_error = str(e)
                
                execution = RuleExecution(
                    execution_id=execution_id,
                    rule_id=rule.rule_id,
                    zone_id=zone_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    conditions_met=False,
                    actions_executed=0,
                    success=False,
                    error=str(e),
                )
            
            executions.append(execution)
            self._executions.append(execution)
            
            # Limit executions (last 1000)
            if len(self._executions) > 1000:
                self._executions = self._executions[-1000:]
        
        return executions
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID."""
        return self._rules.get(rule_id)
    
    def get_rules(self, zone_id: Optional[str] = None,
                 enabled_only: bool = False) -> List[Rule]:
        """Get rules, optionally filtered."""
        rules = list(self._rules.values())
        
        if zone_id is not None:
            rules = [r for r in rules if r.zone_id == zone_id]
        
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        
        return rules
    
    def get_executions(self, rule_id: Optional[str] = None,
                      limit: int = 50) -> List[RuleExecution]:
        """Get rule executions."""
        executions = self._executions
        
        if rule_id:
            executions = [e for e in executions if e.rule_id == rule_id]
        
        return executions[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        total_rules = len(self._rules)
        enabled_rules = len([r for r in self._rules.values() if r.enabled])
        triggered_rules = len([r for r in self._rules.values() if r.last_triggered])
        
        successful_executions = len([e for e in self._executions if e.success])
        failed_executions = len([e for e in self._executions if not e.success])
        
        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": total_rules - enabled_rules,
            "triggered_rules": triggered_rules,
            "total_executions": len(self._executions),
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "registered_modules": len(self._modules),
            "module_connections": len(self._connections),
        }
    
    def apply_module_connections(self) -> int:
        """Apply connections between modules."""
        applied = 0
        
        for conn in self._connections:
            source_context = self._module_contexts.get(conn.source_module, {})
            source_value = source_context.get(conn.source_field)
            
            if source_value is not None:
                # Apply transform if specified
                target_value = source_value
                if conn.transform:
                    target_value = self._apply_transform(conn.transform, source_value)
                
                # Set in target module context
                if conn.target_module in self._module_contexts:
                    self._module_contexts[conn.target_module][conn.target_field] = target_value
                    applied += 1
        
        return applied
    
    def _apply_transform(self, transform: str, value: Any) -> Any:
        """Apply transform function to value."""
        # Simple transforms
        if transform == "bool":
            return bool(value)
        elif transform == "float":
            return float(value)
        elif transform == "int":
            return int(value)
        elif transform == "str":
            return str(value)
        elif transform == "invert":
            return not value
        elif transform.startswith("multiply:"):
            factor = float(transform.split(":")[1])
            return value * factor
        elif transform.startswith("add:"):
            offset = float(transform.split(":")[1])
            return value + offset
        
        return value
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_rules_engine() -> RulesEngine:
    """Factory function to create rules engine."""
    return RulesEngine()


# Pre-built rule templates
def create_presence_light_rule(zone_id: str,
                              brightness_threshold: float = 0.3) -> Rule:
    """Create presence-based light automation rule."""
    return Rule(
        rule_id=f"rule_presence_light_{zone_id}",
        name=f"Auto Light: {zone_id}",
        zone_id=zone_id,
        conditions=[
            Condition(
                field="presence.state",
                operator=RuleOperator.EQ,
                value="present",
                zone_id=zone_id,
            ),
            Condition(
                field="light.level",
                operator=RuleOperator.LT,
                value=brightness_threshold,
                zone_id=zone_id,
            ),
        ],
        connector=RuleConnector.AND,
        actions=[
            Action(
                action_type=ActionType.LIGHT_TURN_ON,
                target_zone=zone_id,
                parameters={"brightness": 0.8},
            ),
        ],
        priority=60,
        cooldown_seconds=60,
        description="Turn on lights when presence detected and low light",
    )


def create_absence_light_off_rule(zone_id: str,
                                  delay_seconds: int = 300) -> Rule:
    """Create absence-based light off rule."""
    return Rule(
        rule_id=f"rule_absence_off_{zone_id}",
        name=f"Auto Off: {zone_id}",
        zone_id=zone_id,
        conditions=[
            Condition(
                field="presence.state",
                operator=RuleOperator.EQ,
                value="absent",
                zone_id=zone_id,
            ),
        ],
        connector=RuleConnector.AND,
        actions=[
            Action(
                action_type=ActionType.LIGHT_TURN_OFF,
                target_zone=zone_id,
            ),
        ],
        priority=50,
        cooldown_seconds=delay_seconds,
        description="Turn off lights when zone is absent",
    )


def create_evening_scene_rule(zone_id: str) -> Rule:
    """Create evening scene rule."""
    return Rule(
        rule_id=f"rule_evening_scene_{zone_id}",
        name=f"Evening Scene: {zone_id}",
        zone_id=zone_id,
        conditions=[
            Condition(
                field="timeofday.phase",
                operator=RuleOperator.EQ,
                value="evening",
                zone_id=zone_id,
            ),
            Condition(
                field="presence.state",
                operator=RuleOperator.EQ,
                value="present",
                zone_id=zone_id,
            ),
        ],
        connector=RuleConnector.AND,
        actions=[
            Action(
                action_type=ActionType.LIGHT_SCENE,
                target_zone=zone_id,
                parameters={"scene": "relaxing"},
            ),
        ],
        priority=70,
        cooldown_seconds=300,
        description="Apply relaxing scene in evening when present",
    )
