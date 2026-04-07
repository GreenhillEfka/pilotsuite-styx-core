"""Rules Engine Extensions — Slice 78.

Erweiterte Regel-Engine für Habituszonen.

New Features (Slice 78):
- Advanced Rule Templates (pre-built automations)
- Rule Chaining (rules triggering rules)
- Conflict Detection (competing rules)
- Rule Dependencies (prerequisites)
- Conditional Actions (if-else within actions)
- Rule Variables (dynamic values)
- Rule Statistics & Analytics
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class RuleTemplateType(Enum):
    """Pre-built rule template types."""
    PRESENCE_LIGHT = "presence_light"  # Auto light on presence
    ABSENCE_OFF = "absence_off"  # Auto off when absent
    SUNRISE_WAKE = "sunrise_wake"  # Sunrise wake-up
    SUNSET_LIGHTS = "sunset_lights"  # Lights at sunset
    AWAY_SECURITY = "away_security"  # Security simulation
    ENERGY_SAVER = "energy_saver"  # Energy optimization
    COMFORT_MODE = "comfort_mode"  # Comfort optimization
    GUEST_MODE = "guest_mode"  # Guest automation
    MORNING_ROUTINE = "morning_routine"  # Morning automation
    EVENING_ROUTINE = "evening_routine"  # Evening automation
    NIGHT_MODE = "night_mode"  # Night automation
    CUSTOM = "custom"


class ConflictType(Enum):
    """Rule conflict types."""
    ACTION_CONFLICT = "action_conflict"  # Same target, different actions
    PRIORITY_CONFLICT = "priority_conflict"  # Same priority, competing
    CONDITION_CONFLICT = "condition_conflict"  # Mutually exclusive conditions
    RESOURCE_CONFLICT = "resource_conflict"  # Same resource contention


class RuleChainNode:
    """Node in a rule chain."""
    def __init__(self, rule_id: str, triggered_by: Optional[str] = None):
        self.rule_id = rule_id
        self.triggered_by = triggered_by
        self.timestamp: str = datetime.now(timezone.utc).isoformat()
        self.success: bool = False
        self.error: Optional[str] = None


@dataclass
class RuleDependency:
    """Rule dependency definition."""
    dependency_id: str
    rule_id: str
    depends_on_rule_ids: List[str]
    condition: str = "all"  # "all" or "any"
    timeout_seconds: int = 0  # 0 = no timeout
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dependency_id": self.dependency_id,
            "rule_id": self.rule_id,
            "depends_on_rule_ids": self.depends_on_rule_ids,
            "condition": self.condition,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class RuleVariable:
    """Dynamic rule variable."""
    name: str
    value_type: str  # "string", "number", "boolean", "expression"
    default_value: Any = None
    expression: Optional[str] = None  # Evaluated expression
    read_only: bool = False
    
    def evaluate(self, context: Dict[str, Any]) -> Any:
        """Evaluate variable value."""
        if self.expression:
            # Simple expression evaluation (safe subset)
            return self._eval_expression(context)
        return self.default_value
    
    def _eval_expression(self, context: Dict[str, Any]) -> Any:
        """Safely evaluate expression."""
        # Very basic expression support - just variable substitution
        expr = self.expression
        for key, value in context.items():
            expr = expr.replace(f"${{{key}}}", str(value))
        
        # Safe eval of simple math
        try:
            # Only allow basic math operations
            allowed_chars = set("0123456789+-*/.() ")
            if all(c in allowed_chars for c in expr):
                return eval(expr)
        except Exception:
            pass
        
        return self.default_value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value_type": self.value_type,
            "default_value": self.default_value,
            "expression": self.expression,
            "read_only": self.read_only,
        }


@dataclass
class ConflictRecord:
    """Recorded rule conflict."""
    conflict_id: str
    conflict_type: ConflictType
    rule_ids: List[str]
    description: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved: bool = False
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "rule_ids": self.rule_ids,
            "description": self.description,
            "detected_at": self.detected_at,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class RuleStatistics:
    """Rule execution statistics."""
    rule_id: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_ms: float = 0.0
    last_execution: Optional[str] = None
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    trigger_count: int = 0
    conditions_met_count: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "average_execution_ms": self.average_execution_ms,
            "last_execution": self.last_execution,
            "trigger_count": self.trigger_count,
            "conditions_met_count": self.conditions_met_count,
        }


class CappedConflictList(list):
    """List with a fixed maximum size for conflict records."""

    def __init__(self, max_size: int = 1000):
        super().__init__()
        self.max_size = max_size

    def _trim(self) -> None:
        excess = len(self) - self.max_size
        if excess > 0:
            del self[:excess]

    def append(self, item):
        super().append(item)
        self._trim()

    def extend(self, items):
        super().extend(items)
        self._trim()

class RulesEngineExtended:
    """Extended rules engine with advanced features.
    
    New Capabilities (Slice 78):
    - Pre-built rule templates
    - Rule chaining (rules triggering rules)
    - Conflict detection and resolution
    - Rule dependencies
    - Dynamic variables
    - Execution statistics
    
    All features are modular — no central config dependency.
    """
    
    def __init__(self):
        self._rules: Dict[str, Any] = {}  # rule_id -> Rule (from base engine)
        self._templates: Dict[RuleTemplateType, Callable] = {}
        self._dependencies: Dict[str, RuleDependency] = {}
        self._variables: Dict[str, RuleVariable] = {}
        self._conflicts: List[ConflictRecord] = CappedConflictList(max_size=1000)
        self._statistics: Dict[str, RuleStatistics] = {}
        self._chain_history: Dict[str, List[RuleChainNode]] = {}  # root_rule_id -> chain
        self._rule_chains: Dict[str, List[str]] = {}  # rule_id -> triggered rules
        
        self._register_default_templates()
        
        logger.info("RulesEngineExtended initialized")
    
    def _register_default_templates(self) -> None:
        """Register default rule templates."""
        self._templates[RuleTemplateType.PRESENCE_LIGHT] = self._template_presence_light
        self._templates[RuleTemplateType.ABSENCE_OFF] = self._template_absence_off
        self._templates[RuleTemplateType.SUNRISE_WAKE] = self._template_sunrise_wake
        self._templates[RuleTemplateType.SUNSET_LIGHTS] = self._template_sunset_lights
        self._templates[RuleTemplateType.AWAY_SECURITY] = self._template_away_security
        self._templates[RuleTemplateType.ENERGY_SAVER] = self._template_energy_saver
        self._templates[RuleTemplateType.MORNING_ROUTINE] = self._template_morning_routine
        self._templates[RuleTemplateType.EVENING_ROUTINE] = self._template_evening_routine
        self._templates[RuleTemplateType.NIGHT_MODE] = self._template_night_mode
    
    def register_template(self, template_type: RuleTemplateType,
                         factory: Callable) -> None:
        """Register a rule template factory."""
        self._templates[template_type] = factory
    
    def create_rule_from_template(self, template_type: RuleTemplateType,
                                  zone_id: str,
                                  **kwargs) -> Optional[Any]:
        """Create a rule from a template."""
        factory = self._templates.get(template_type)
        
        if not factory:
            logger.error("Unknown template type: %s", getattr(template_type, "value", template_type))
            return None
        
        try:
            rule = factory(zone_id, **kwargs)
            return rule
        except Exception as e:
            logger.exception("Template creation failed: %s", e)
            return None
    
    def _template_presence_light(self, zone_id: str, **kwargs) -> Any:
        """Create presence-based light automation rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        brightness_threshold = kwargs.get("brightness_threshold", 0.3)
        cooldown = kwargs.get("cooldown_seconds", 60)
        
        return Rule(
            rule_id=f"rule_presence_light_{zone_id}",
            name=f"Auto Light: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("presence.state", RuleOperator.EQ, "present", zone_id),
                Condition("light.level", RuleOperator.LT, brightness_threshold, zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_TURN_ON, zone_id, {"brightness": 0.8}),
            ],
            priority=60,
            cooldown_seconds=cooldown,
            description="Turn on lights when presence detected and low light",
        )
    
    def _template_absence_off(self, zone_id: str, **kwargs) -> Any:
        """Create absence-based light off rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        delay = kwargs.get("delay_seconds", 300)
        
        return Rule(
            rule_id=f"rule_absence_off_{zone_id}",
            name=f"Auto Off: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("presence.state", RuleOperator.EQ, "absent", zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_TURN_OFF, zone_id),
            ],
            priority=50,
            cooldown_seconds=delay,
            description="Turn off lights when zone is absent",
        )
    
    def _template_sunrise_wake(self, zone_id: str, **kwargs) -> Any:
        """Create sunrise wake-up rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        brightness = kwargs.get("brightness", 0.6)
        
        return Rule(
            rule_id=f"rule_sunrise_wake_{zone_id}",
            name=f"Sunrise Wake: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("timeofday.event", RuleOperator.EQ, "sunrise", zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_TURN_ON, zone_id, {"brightness": brightness}),
            ],
            priority=70,
            cooldown_seconds=300,
            description="Wake up with sunrise",
        )
    
    def _template_sunset_lights(self, zone_id: str, **kwargs) -> Any:
        """Create sunset lights rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        return Rule(
            rule_id=f"rule_sunset_lights_{zone_id}",
            name=f"Sunset Lights: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("timeofday.event", RuleOperator.EQ, "sunset", zone_id),
                Condition("presence.state", RuleOperator.EQ, "present", zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_TURN_ON, zone_id, {"brightness": 0.7}),
            ],
            priority=65,
            cooldown_seconds=300,
            description="Turn on lights at sunset",
        )
    
    def _template_away_security(self, zone_id: str, **kwargs) -> Any:
        """Create away security simulation rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        return Rule(
            rule_id=f"rule_away_security_{zone_id}",
            name=f"Away Security: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("presence.state", RuleOperator.EQ, "extended_absent", zone_id),
                Condition("timeofday.phase", RuleOperator.EQ, "night", zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_TURN_ON, zone_id, {"brightness": 0.5, "duration": 1800}),
            ],
            priority=40,
            cooldown_seconds=3600,
            description="Security lighting when away",
        )
    
    def _template_energy_saver(self, zone_id: str, **kwargs) -> Any:
        """Create energy saver rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        return Rule(
            rule_id=f"rule_energy_saver_{zone_id}",
            name=f"Energy Saver: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("light.brightness", RuleOperator.GT, 0.9, zone_id),
                Condition("presence.state", RuleOperator.EQ, "present", zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_DIM, zone_id, {"brightness": 0.7}),
            ],
            priority=30,
            cooldown_seconds=600,
            description="Reduce brightness for energy saving",
        )
    
    def _template_morning_routine(self, zone_id: str, **kwargs) -> Any:
        """Create morning routine rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        return Rule(
            rule_id=f"rule_morning_routine_{zone_id}",
            name=f"Morning Routine: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("timeofday.phase", RuleOperator.EQ, "morning", zone_id),
                Condition("presence.state", RuleOperator.EQ, "present", zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_SCENE, zone_id, {"scene": "morning"}),
            ],
            priority=55,
            cooldown_seconds=600,
            description="Morning automation routine",
        )
    
    def _template_evening_routine(self, zone_id: str, **kwargs) -> Any:
        """Create evening routine rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        return Rule(
            rule_id=f"rule_evening_routine_{zone_id}",
            name=f"Evening Routine: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("timeofday.phase", RuleOperator.EQ, "evening", zone_id),
                Condition("presence.state", RuleOperator.EQ, "present", zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_SCENE, zone_id, {"scene": "relaxing"}),
            ],
            priority=55,
            cooldown_seconds=600,
            description="Evening automation routine",
        )
    
    def _template_night_mode(self, zone_id: str, **kwargs) -> Any:
        """Create night mode rule."""
        from copilot_core.orchestration.rules_engine import (
            Rule, Condition, Action, RuleOperator, RuleConnector, ActionType
        )
        
        return Rule(
            rule_id=f"rule_night_mode_{zone_id}",
            name=f"Night Mode: {zone_id}",
            zone_id=zone_id,
            conditions=[
                Condition("timeofday.phase", RuleOperator.IN, ["night", "late_night"], zone_id),
            ],
            connector=RuleConnector.AND,
            actions=[
                Action(ActionType.LIGHT_DIM, zone_id, {"brightness": 0.1}),
            ],
            priority=50,
            cooldown_seconds=300,
            description="Night mode automation",
        )
    
    def add_dependency(self, dependency: RuleDependency) -> bool:
        """Add rule dependency."""
        if dependency.rule_id in self._dependencies:
            return False
        
        with self._lock():
            self._dependencies[dependency.rule_id] = dependency
        
        return True
    
    def remove_dependency(self, rule_id: str) -> bool:
        """Remove rule dependency."""
        if rule_id not in self._dependencies:
            return False
        
        with self._lock():
            del self._dependencies[rule_id]
        
        return True
    
    def check_dependencies(self, rule_id: str,
                          execution_results: Dict[str, bool]) -> bool:
        """Check if rule dependencies are satisfied."""
        dependency = self._dependencies.get(rule_id)
        
        if not dependency:
            return True  # No dependencies
        
        dep_results = [
            execution_results.get(dep_rule, False)
            for dep_rule in dependency.depends_on_rule_ids
        ]
        
        if dependency.condition == "all":
            return all(dep_results)
        else:  # "any"
            return any(dep_results)
    
    def add_variable(self, variable: RuleVariable) -> bool:
        """Add rule variable."""
        if variable.name in self._variables:
            return False
        
        with self._lock():
            self._variables[variable.name] = variable
        
        return True
    
    def get_variable(self, name: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Get variable value."""
        variable = self._variables.get(name)
        
        if not variable:
            return None
        
        return variable.evaluate(context or {})
    
    def detect_conflicts(self, rules: List[Any]) -> List[ConflictRecord]:
        """Detect conflicts between rules."""
        conflicts = []
        
        # Check for action conflicts (same zone, competing actions)
        zone_actions: Dict[str, List[Tuple[str, Any]]] = {}
        
        for rule in rules:
            if not hasattr(rule, 'zone_id') or not hasattr(rule, 'actions'):
                continue
            
            zone_id = rule.zone_id
            if zone_id not in zone_actions:
                zone_actions[zone_id] = []
            
            for action in rule.actions:
                zone_actions[zone_id].append((rule.rule_id, action))
        
        # Detect conflicts
        for zone_id, action_list in zone_actions.items():
            if len(action_list) < 2:
                continue
            
            # Check for competing actions
            turn_on_rules = [r for r, a in action_list if a.action_type.value == "light.turn_on"]
            turn_off_rules = [r for r, a in action_list if a.action_type.value == "light.turn_off"]
            
            if turn_on_rules and turn_off_rules:
                conflict = ConflictRecord(
                    conflict_id=f"conflict_{uuid.uuid4().hex[:16]}",
                    conflict_type=ConflictType.ACTION_CONFLICT,
                    rule_ids=turn_on_rules + turn_off_rules,
                    description=f"Competing on/off actions in {zone_id}",
                )
                conflicts.append(conflict)
        
        # Store conflicts
        with self._lock():
            self._conflicts.extend(conflicts)
            
            # Limit history
            if len(self._conflicts) > 1000:
                self._conflicts = self._conflicts[-1000:]
        
        return conflicts
    
    def resolve_conflict(self, conflict_id: str, resolution: str) -> bool:
        """Mark a conflict as resolved."""
        for conflict in self._conflicts:
            if conflict.conflict_id == conflict_id:
                conflict.resolved = True
                conflict.resolution = resolution
                return True
        
        return False
    
    def record_execution(self, rule_id: str, success: bool,
                        execution_ms: float) -> None:
        """Record rule execution for statistics."""
        if rule_id not in self._statistics:
            self._statistics[rule_id] = RuleStatistics(rule_id=rule_id)
        
        stats = self._statistics[rule_id]
        now = datetime.now(timezone.utc).isoformat()
        
        stats.total_executions += 1
        stats.last_execution = now
        
        if success:
            stats.successful_executions += 1
            stats.last_success = now
        else:
            stats.failed_executions += 1
            stats.last_failure = now
        
        # Update average execution time
        stats.average_execution_ms = (
            (stats.average_execution_ms * (stats.total_executions - 1) + execution_ms)
            / stats.total_executions
        )
    
    def record_trigger(self, rule_id: str) -> None:
        """Record rule trigger."""
        if rule_id not in self._statistics:
            self._statistics[rule_id] = RuleStatistics(rule_id=rule_id)
        
        self._statistics[rule_id].trigger_count += 1
    
    def record_condition_met(self, rule_id: str) -> None:
        """Record condition evaluation."""
        if rule_id not in self._statistics:
            self._statistics[rule_id] = RuleStatistics(rule_id=rule_id)
        
        self._statistics[rule_id].conditions_met_count += 1
    
    def add_rule_chain(self, trigger_rule_id: str,
                      triggered_rule_ids: List[str]) -> bool:
        """Add rule chain (rule triggering other rules)."""
        if trigger_rule_id in self._rule_chains:
            return False
        
        with self._lock():
            self._rule_chains[trigger_rule_id] = triggered_rule_ids
        
        return True
    
    def execute_chain(self, root_rule_id: str) -> List[RuleChainNode]:
        """Execute a rule chain."""
        chain = []
        
        triggered_rules = self._rule_chains.get(root_rule_id, [])
        
        for rule_id in triggered_rules:
            node = RuleChainNode(rule_id, triggered_by=root_rule_id)
            chain.append(node)
        
        if chain:
            with self._lock():
                if root_rule_id not in self._chain_history:
                    self._chain_history[root_rule_id] = []
                self._chain_history[root_rule_id].extend(chain)
        
        return chain
    
    def get_statistics(self, rule_id: Optional[str] = None) -> Dict[str, Any]:
        """Get rules engine statistics."""
        if rule_id:
            stats = self._statistics.get(rule_id)
            return stats.to_dict() if stats else {}
        
        total_rules = len(self._statistics)
        total_executions = sum(s.total_executions for s in self._statistics.values())
        total_success = sum(s.successful_executions for s in self._statistics.values())
        
        return {
            "total_rules_tracked": total_rules,
            "total_executions": total_executions,
            "total_success": total_success,
            "total_failures": total_executions - total_success,
            "overall_success_rate": total_success / total_executions if total_executions > 0 else 0.0,
            "active_dependencies": len(self._dependencies),
            "total_variables": len(self._variables),
            "conflicts_detected": len([c for c in self._conflicts if not c.resolved]),
            "conflicts_resolved": len([c for c in self._conflicts if c.resolved]),
            "rule_chains": len(self._rule_chains),
        }
    
    def get_conflicts(self, unresolved_only: bool = True) -> List[ConflictRecord]:
        """Get detected conflicts."""
        if unresolved_only:
            return [c for c in self._conflicts if not c.resolved]
        return self._conflicts.copy()
    
    def get_chain_history(self, root_rule_id: str) -> List[RuleChainNode]:
        """Get chain execution history."""
        return self._chain_history.get(root_rule_id, [])
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_rules_engine_extended() -> RulesEngineExtended:
    """Factory function to create extended rules engine."""
    return RulesEngineExtended()
