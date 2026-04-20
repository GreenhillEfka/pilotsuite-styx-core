"""
Automation Rule Engine — F4.6
PilotSuite's own rule-matching engine independent of HA native automations.

Provides:
- AutomationRule dataclass with condition/action pairs
- RuleMatcher: evaluates rules against current brain graph state
- RuleExecutor: fires actions via HA bridge
- CRUD API for managing user-defined rules
- Predefined default rules (energy, presence, safety)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class RuleStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    TRIGGERED = "triggered"
    ERROR = "error"


class ConditionOp(Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


@dataclass
class RuleCondition:
    field: str
    operator: ConditionOp = ConditionOp.EQ
    value: Any = None

    def evaluate(self, ctx: Dict[str, Any]) -> bool:
        field_val = self._resolve_field(ctx)
        if field_val is None:
            return False
        try:
            if self.operator == ConditionOp.EQ:
                return field_val == self.value
            elif self.operator == ConditionOp.NE:
                return field_val != self.value
            elif self.operator == ConditionOp.GT:
                return float(field_val) > float(self.value)
            elif self.operator == ConditionOp.GE:
                return float(field_val) >= float(self.value)
            elif self.operator == ConditionOp.LT:
                return float(field_val) < float(self.value)
            elif self.operator == ConditionOp.LE:
                return float(field_val) <= float(self.value)
            elif self.operator == ConditionOp.IN:
                vals = self.value if isinstance(self.value, (list, tuple)) else [self.value]
                return field_val in vals
            elif self.operator == ConditionOp.NOT_IN:
                vals = self.value if isinstance(self.value, (list, tuple)) else [self.value]
                return field_val not in vals
            elif self.operator == ConditionOp.CONTAINS:
                return str(self.value) in str(field_val)
        except (ValueError, TypeError):
            pass
        return False

    def _resolve_field(self, ctx: Dict[str, Any]) -> Any:
        parts = self.field.split(".")
        val = ctx
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                return None
        return val


@dataclass
class RuleAction:
    action_type: str
    entity_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutomationRule:
    rule_id: str
    name: str
    description: str = ""
    conditions: List[RuleCondition] = field(default_factory=list)
    actions: List[RuleAction] = field(default_factory=list)
    status: RuleStatus = RuleStatus.ACTIVE
    created_at_ms: int = 0
    last_triggered_ms: int = 0
    trigger_count: int = 0
    cooldown_seconds: int = 60
    require_all_conditions: bool = True
    tags: List[str] = field(default_factory=list)
    priority: int = 0

    def __post_init__(self):
        if not self.created_at_ms:
            self.created_at_ms = int(time.time() * 1000)

    def matches(self, ctx: Dict[str, Any]) -> bool:
        if not self.conditions:
            return False
        if self.require_all_conditions:
            return all(c.evaluate(ctx) for c in self.conditions)
        return any(c.evaluate(ctx) for c in self.conditions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "conditions": [{"field": c.field, "operator": c.operator.value, "value": c.value} for c in self.conditions],
            "actions": [{"action_type": a.action_type, "entity_id": a.entity_id, "params": a.params} for a in self.actions],
            "status": self.status.value,
            "created_at_ms": self.created_at_ms,
            "last_triggered_ms": self.last_triggered_ms,
            "trigger_count": self.trigger_count,
            "cooldown_seconds": self.cooldown_seconds,
            "require_all_conditions": self.require_all_conditions,
            "tags": self.tags,
            "priority": self.priority,
        }


class RuleMatcher:
    def __init__(self):
        self._rules: Dict[str, AutomationRule] = {}
        self._default_rules_loaded = False

    def add_rule(self, rule: AutomationRule) -> None:
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        return self._rules.get(rule_id)

    def list_rules(self, tag: Optional[str] = None, status: Optional[RuleStatus] = None) -> List[AutomationRule]:
        result = list(self._rules.values())
        if tag:
            result = [r for r in result if tag in r.tags]
        if status:
            result = [r for r in result if r.status == status]
        return sorted(result, key=lambda r: r.priority, reverse=True)

    def match_all(self, ctx: Dict[str, Any]) -> List[AutomationRule]:
        now_ms = int(time.time() * 1000)
        matched = []
        for rule in self._rules.values():
            if rule.status != RuleStatus.ACTIVE:
                continue
            if rule.last_triggered_ms and (now_ms - rule.last_triggered_ms) < (rule.cooldown_seconds * 1000):
                continue
            if rule.matches(ctx):
                matched.append(rule)
        return matched

    def load_defaults(self) -> None:
        if self._default_rules_loaded:
            return
        self.add_rule(AutomationRule(
            rule_id="energy_solar_surplus",
            name="Solar Surplus Alert",
            description="Aktiviere Energie-Dispatch wenn PV-Überschuss > 2kW",
            conditions=[RuleCondition(field="pv.power_kw", operator=ConditionOp.GT, value=2.0)],
            actions=[RuleAction(action_type="notify", params={"message": "PV-Überschuss — Ladung aktivieren?"})],
            tags=["energy", "solar"], priority=80,
        ))
        self.add_rule(AutomationRule(
            rule_id="anomaly_high_alert",
            name="Anomaly Alert",
            description="Hohe Anomalie → Benachrichtigung",
            conditions=[RuleCondition(field="anomaly.score", operator=ConditionOp.LT, value=-0.7)],
            actions=[RuleAction(action_type="notify", params={"message": "Anomalie erkannt"})],
            tags=["security", "anomaly"], priority=90,
        ))
        self.add_rule(AutomationRule(
            rule_id="zone_entry_comfort",
            name="Zone Entry Comfort",
            description="Zone betreten → Komfort prüfen",
            conditions=[RuleCondition(field="presence.event", operator=ConditionOp.EQ, value="arrive")],
            actions=[RuleAction(action_type="query", entity_id="climate.current", params={})],
            tags=["presence", "comfort"], priority=50,
        ))
        self.add_rule(AutomationRule(
            rule_id="safety_alarm",
            name="Safety Alarm",
            description="Sicherheitsalarm → sofortige Benachrichtigung",
            conditions=[RuleCondition(field="sensor.safety_alarm", operator=ConditionOp.EQ, value=True)],
            actions=[RuleAction(action_type="notify", params={"message": "SICHERHEITSALARM!", "priority": "critical"})],
            tags=["safety", "critical"], priority=100,
        ))
        self._default_rules_loaded = True
        logger.info("Default automation rules loaded: %d rules", len(self._rules))


class RuleExecutor:
    def __init__(self, ha_bridge=None):
        self._ha_bridge = ha_bridge
        self._execution_log: List[Dict[str, Any]] = []
        self._max_log = 200

    def execute(self, rule: AutomationRule, ctx: Dict[str, Any]) -> Dict[str, Any]:
        results = []
        for action in rule.actions:
            try:
                result = self._execute_action(action, ctx)
                results.append({"action": action.action_type, "entity": action.entity_id, "ok": True, "result": result})
            except Exception as e:
                results.append({"action": action.action_type, "entity": action.entity_id, "ok": False, "error": str(e)})
        now_ms = int(time.time() * 1000)
        rule.last_triggered_ms = now_ms
        rule.trigger_count += 1
        self._execution_log.append({"rule_id": rule.rule_id, "ts_ms": now_ms, "ctx": ctx, "results": results})
        if len(self._execution_log) > self._max_log:
            self._execution_log = self._execution_log[-self._max_log:]
        return {"rule_id": rule.rule_id, "rule_name": rule.name, "executed_at_ms": now_ms, "action_results": results, "trigger_count": rule.trigger_count}

    def _execute_action(self, action: RuleAction, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if action.action_type == "notify":
            from copilot_core.proactive_engine import ProactiveContextEngine
            pe = ProactiveContextEngine()
            msg = action.params.get("message", "Automation triggered")
            for k, v in ctx.items():
                msg = msg.replace(f"{{{k}}}", str(v))
            pe.deliver_suggestion({"type": "automation", "message": msg}, method="notification")
            return {"notified": True, "message": msg}
        elif action.action_type == "adjust":
            return {"adjusted": True, "entity_id": action.entity_id, "params": action.params}
        elif action.action_type == "ha_call" and self._ha_bridge:
            try:
                parts = action.entity_id.split(".")
                domain, service = parts[0], parts[-1] if len(parts) > 1 else action.entity_id
                return self._ha_bridge.call_service(domain, service, action.params)
            except Exception as e:
                return {"error": str(e)}
        return {"delivered": True, "method": action.action_type}

    def get_execution_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._execution_log[-limit:]
