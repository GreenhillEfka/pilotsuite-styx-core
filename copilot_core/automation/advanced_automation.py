"""Advanced Automation — Complex Workflows, Multi-Step, Conditional Logic."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """Automation trigger types."""
    TIME = "time"
    EVENT = "event"
    STATE = "state"
    WEBHOOK = "webhook"
    VOICE = "voice"
    PRESENCE = "presence"
    COMPOSITE = "composite"


class ConditionOperator(Enum):
    """Condition operators."""
    AND = "and"
    OR = "or"
    NOT = "not"
    XOR = "xor"


@dataclass
class Trigger:
    """Automation trigger."""
    id: str
    trigger_type: TriggerType
    config: Dict[str, Any]
    enabled: bool = True


@dataclass
class Condition:
    """Automation condition."""
    id: str
    entity_id: str
    attribute: str
    operator: str  # eq, ne, gt, lt, contains
    value: Any
    logical_op: ConditionOperator = ConditionOperator.AND


@dataclass
class Action:
    """Automation action."""
    id: str
    action_type: str  # service_call, script, scene, notification
    target: str
    data: Dict[str, Any]
    parallel: bool = False


@dataclass
class Automation:
    """Complete automation definition."""
    id: str
    name: str
    description: str
    triggers: List[Trigger] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    enabled: bool = True
    mode: str = "single"  # single, restart, queued, parallel
    max_runs: int = 10


class AdvancedAutomationEngine:
    """Advanced automation engine with complex workflows."""

    def __init__(self):
        self._automations: Dict[str, Automation] = {}
        self._running_automations: Dict[str, int] = {}
        self._execution_history: List[Dict] = []
        self._action_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default action handlers."""
        self._action_handlers = {
            "service_call": self._handle_service_call,
            "script": self._handle_script,
            "scene": self._handle_scene,
            "notification": self._handle_notification,
            "delay": self._handle_delay,
            "wait_for_trigger": self._handle_wait_trigger,
            "repeat": self._handle_repeat,
            "choose": self._handle_choose,
        }

    def create_automation(self, automation: Automation) -> str:
        """Create a new automation."""
        self._automations[automation.id] = automation
        logger.info(f"Created automation: {automation.name} ({automation.id})")
        return automation.id

    def create_morning_routine(self, user_id: str, zone_id: str) -> Automation:
        """Create a morning routine automation."""
        automation = Automation(
            id=f"morning_routine_{user_id}",
            name="Morning Routine",
            description="Automated morning wake-up sequence",
            triggers=[
                Trigger(
                    id="sunrise",
                    trigger_type=TriggerType.TIME,
                    config={"event": "sunrise", "offset": "-00:30:00"}
                ),
                Trigger(
                    id="alarm",
                    trigger_type=TriggerType.EVENT,
                    config={"event": "alarm_clock", "user_id": user_id}
                ),
            ],
            conditions=[
                Condition(
                    id="weekday",
                    entity_id="sensor.date",
                    attribute="day_of_week",
                    operator="in",
                    value=["mon", "tue", "wed", "thu", "fri"]
                ),
                Condition(
                    id="home",
                    entity_id=f"presence.{user_id}",
                    attribute="state",
                    operator="eq",
                    value="home"
                ),
            ],
            actions=[
                Action(
                    id="lights_slow_on",
                    action_type="service_call",
                    target="light.bedroom",
                    data={"service": "turn_on", "brightness_pct": 10, "transition": 300}
                ),
                Action(
                    id="blinds_open",
                    action_type="service_call",
                    target="cover.bedroom",
                    data={"service": "open_cover", "position": 50}
                ),
                Action(
                    id="thermostat_comfort",
                    action_type="service_call",
                    target="climate.home",
                    data={"service": "set_temperature", "temperature": 21}
                ),
                Action(
                    id="coffee_start",
                    action_type="service_call",
                    target="switch.coffee_machine",
                    data={"service": "turn_on"}
                ),
                Action(
                    id="news_brief",
                    action_type="notification",
                    target=user_id,
                    data={"title": "Guten Morgen", "message": "Wetter und News folgen..."}
                ),
            ],
            mode="queued",
            max_runs=1,
        )
        
        return self.create_automation(automation)

    def create_evening_routine(self, user_id: str, zone_id: str) -> Automation:
        """Create an evening routine automation."""
        automation = Automation(
            id=f"evening_routine_{user_id}",
            name="Evening Routine",
            description="Automated evening wind-down sequence",
            triggers=[
                Trigger(
                    id="sunset",
                    trigger_type=TriggerType.TIME,
                    config={"event": "sunset", "offset": "+00:15:00"}
                ),
                Trigger(
                    id="bedtime",
                    trigger_type=TriggerType.TIME,
                    config={"time": "22:00:00"}
                ),
            ],
            conditions=[
                Condition(
                    id="home",
                    entity_id=f"presence.{user_id}",
                    attribute="state",
                    operator="eq",
                    value="home"
                ),
            ],
            actions=[
                Action(
                    id="lights_dim",
                    action_type="service_call",
                    target="light.living_room",
                    data={"service": "turn_on", "brightness_pct": 30, "color_temp": 400}
                ),
                Action(
                    id="thermostat_night",
                    action_type="service_call",
                    target="climate.home",
                    data={"service": "set_temperature", "temperature": 19}
                ),
                Action(
                    id="lock_doors",
                    action_type="service_call",
                    target="lock.front_door",
                    data={"service": "lock"}
                ),
                Action(
                    id="security_arm",
                    action_type="service_call",
                    target="alarm_control_panel.home",
                    data={"service": "alarm_arm_night"}
                ),
            ],
            mode="single",
        )
        
        return self.create_automation(automation)

    def create_presence_automation(self, user_id: str, zone_id: str) -> Automation:
        """Create presence-based automation."""
        automation = Automation(
            id=f"presence_{user_id}_{zone_id}",
            name=f"Presence: {zone_id}",
            description="Automated actions when entering/leaving zone",
            triggers=[
                Trigger(
                    id="enter",
                    trigger_type=TriggerType.PRESENCE,
                    config={"user_id": user_id, "zone_id": zone_id, "event": "enter"}
                ),
                Trigger(
                    id="leave",
                    trigger_type=TriggerType.PRESENCE,
                    config={"user_id": user_id, "zone_id": zone_id, "event": "leave"}
                ),
            ],
            actions=[
                Action(
                    id="enter_lights",
                    action_type="service_call",
                    target=f"light.{zone_id}",
                    data={"service": "turn_on", "brightness_pct": 80}
                ),
                Action(
                    id="leave_lights",
                    action_type="service_call",
                    target=f"light.{zone_id}",
                    data={"service": "turn_off"}
                ),
            ],
            mode="restart",
        )
        
        return self.create_automation(automation)

    async def execute_automation(self, automation_id: str, context: Optional[Dict] = None) -> bool:
        """Execute an automation."""
        if automation_id not in self._automations:
            logger.error(f"Automation not found: {automation_id}")
            return False
        
        automation = self._automations[automation_id]
        
        if not automation.enabled:
            logger.info(f"Automation disabled: {automation_id}")
            return False
        
        # Check running count
        current_runs = self._running_automations.get(automation_id, 0)
        if current_runs >= automation.max_runs:
            logger.warning(f"Max runs reached for {automation_id}")
            return False
        
        # Check conditions
        conditions_met = await self._evaluate_conditions(automation.conditions)
        if not conditions_met:
            logger.info(f"Conditions not met for {automation_id}")
            return False
        
        # Execute actions
        self._running_automations[automation_id] = current_runs + 1
        
        try:
            if automation.mode == "parallel":
                # Execute all actions in parallel
                await asyncio.gather(*[
                    self._execute_action(action, context)
                    for action in automation.actions
                ])
            else:
                # Execute actions sequentially
                for action in automation.actions:
                    await self._execute_action(action, context)
            
            logger.info(f"Automation {automation_id} completed successfully")
            self._execution_history.append({
                "automation_id": automation_id,
                "timestamp": __import__('time').time(),
                "status": "success",
            })
            return True
            
        except Exception as e:
            logger.error(f"Automation {automation_id} failed: {e}")
            self._execution_history.append({
                "automation_id": automation_id,
                "timestamp": __import__('time').time(),
                "status": "failed",
                "error": str(e),
            })
            return False
        finally:
            self._running_automations[automation_id] -= 1

    async def _evaluate_conditions(self, conditions: List[Condition]) -> bool:
        """Evaluate automation conditions."""
        if not conditions:
            return True
        
        results = []
        for cond in conditions:
            # Simulated condition evaluation
            # In production, would query actual entity states
            result = True  # Placeholder
            results.append(result)
        
        # Apply logical operators
        if all(c.logical_op == ConditionOperator.AND for c in conditions):
            return all(results)
        elif any(c.logical_op == ConditionOperator.OR for c in conditions):
            return any(results)
        
        return all(results)

    async def _execute_action(self, action: Action, context: Optional[Dict] = None):
        """Execute a single action."""
        handler = self._action_handlers.get(action.action_type)
        if not handler:
            raise ValueError(f"Unknown action type: {action.action_type}")
        
        await handler(action, context)

    async def _handle_service_call(self, action: Action, context: Optional[Dict]):
        """Handle service call action."""
        logger.info(f"Service call: {action.target} - {action.data}")

    async def _handle_script(self, action: Action, context: Optional[Dict]):
        """Handle script action."""
        logger.info(f"Script: {action.target}")

    async def _handle_scene(self, action: Action, context: Optional[Dict]):
        """Handle scene action."""
        logger.info(f"Scene: {action.target}")

    async def _handle_notification(self, action: Action, context: Optional[Dict]):
        """Handle notification action."""
        logger.info(f"Notification to {action.target}: {action.data}")

    async def _handle_delay(self, action: Action, context: Optional[Dict]):
        """Handle delay action."""
        delay_seconds = action.data.get("seconds", 0)
        await asyncio.sleep(delay_seconds)

    async def _handle_wait_trigger(self, action: Action, context: Optional[Dict]):
        """Handle wait-for-trigger action."""
        logger.info(f"Waiting for trigger: {action.data}")

    async def _handle_repeat(self, action: Action, context: Optional[Dict]):
        """Handle repeat action."""
        count = action.data.get("count", 1)
        for _ in range(count):
            await self._execute_action(Action(**action.data), context)

    async def _handle_choose(self, action: Action, context: Optional[Dict]):
        """Handle choose (conditional) action."""
        choices = action.data.get("choices", [])
        for choice in choices:
            if await self._evaluate_conditions(choice.get("conditions", [])):
                for sub_action in choice.get("sequence", []):
                    await self._execute_action(Action(**sub_action), context)
                break

    def get_automation(self, automation_id: str) -> Optional[Automation]:
        """Get automation by ID."""
        return self._automations.get(automation_id)

    def list_automations(self) -> List[Dict]:
        """List all automations."""
        return [
            {
                "id": a.id,
                "name": a.name,
                "enabled": a.enabled,
                "triggers": len(a.triggers),
                "conditions": len(a.conditions),
                "actions": len(a.actions),
            }
            for a in self._automations.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get automation statistics."""
        return {
            "total_automations": len(self._automations),
            "running_count": sum(self._running_automations.values()),
            "executions": len(self._execution_history),
        }


# Global default advanced automation engine
default_advanced_automation: Optional[AdvancedAutomationEngine] = None


def init_advanced_automation() -> AdvancedAutomationEngine:
    """Initialize global advanced automation engine."""
    global default_advanced_automation
    default_advanced_automation = AdvancedAutomationEngine()
    return default_advanced_automation
