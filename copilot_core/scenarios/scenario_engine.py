"""Custom Scenarios — User-Defined Routines, One-Click Actions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import time
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ScenarioCategory(Enum):
    """Scenario categories."""
    MORNING = "morning"
    EVENING = "evening"
    AWAY = "away"
    PARTY = "party"
    MOVIE = "movie"
    SLEEP = "sleep"
    CUSTOM = "custom"


@dataclass
class ScenarioAction:
    """Action within a scenario."""
    entity_id: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    delay_seconds: float = 0.0


@dataclass
class Scenario:
    """User-defined scenario/routine."""
    id: str
    name: str
    description: str
    category: ScenarioCategory
    icon: str = "mdi:star"
    actions: List[ScenarioAction] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    enabled: bool = True
    usage_count: int = 0
    last_used: Optional[float] = None


class ScenarioEngine:
    """Manages user-defined scenarios and one-click actions."""

    def __init__(self, storage_path: str = "/config/scenarios"):
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._scenarios: Dict[str, Scenario] = {}
        self._execution_handlers: Dict[str, Callable] = {}
        self._register_default_scenarios()

    def _register_default_scenarios(self):
        """Register default scenarios."""
        defaults = [
            Scenario(
                id="good_morning",
                name="Guten Morgen",
                description="Start the day right",
                category=ScenarioCategory.MORNING,
                icon="mdi:weather-sunny",
                actions=[
                    ScenarioAction("light.living_room", "turn_on", {"brightness_pct": 80}),
                    ScenarioAction("cover.bedroom", "open"),
                    ScenarioAction("climate.home", "set_temperature", {"temperature": 22}),
                    ScenarioAction("media_player.kitchen", "play", {"station": "radio_morning"}),
                ],
            ),
            Scenario(
                id="good_night",
                name="Gute Nacht",
                description="Wind down for sleep",
                category=ScenarioCategory.SLEEP,
                icon="mdi:moon-waning-crescent",
                actions=[
                    ScenarioAction("light.all", "turn_off"),
                    ScenarioAction("climate.home", "set_temperature", {"temperature": 19}),
                    ScenarioAction("lock.front_door", "lock"),
                    ScenarioAction("alarm.home", "arm_night"),
                ],
            ),
            Scenario(
                id="movie_night",
                name="Filmabend",
                description="Perfect movie ambiance",
                category=ScenarioCategory.MOVIE,
                icon="mdi:movie",
                actions=[
                    ScenarioAction("light.living_room", "turn_on", {"brightness_pct": 20}),
                    ScenarioAction("media_player.tv", "power_on"),
                    ScenarioAction("climate.living_room", "set_temperature", {"temperature": 21}),
                ],
            ),
            Scenario(
                id="away_mode",
                name="Abwesend",
                description="Secure home when leaving",
                category=ScenarioCategory.AWAY,
                icon="mdi:home-export-outline",
                actions=[
                    ScenarioAction("light.all", "turn_off"),
                    ScenarioAction("climate.home", "set_temperature", {"temperature": 18}),
                    ScenarioAction("lock.all_doors", "lock"),
                    ScenarioAction("alarm.home", "arm_away"),
                ],
            ),
        ]
        
        for scenario in defaults:
            self._scenarios[scenario.id] = scenario

    def create_scenario(self, scenario: Scenario) -> str:
        """Create a new scenario."""
        self._scenarios[scenario.id] = scenario
        self._save_to_disk(scenario)
        logger.info(f"Scenario created: {scenario.name}")
        return scenario.id

    async def execute_scenario(self, scenario_id: str) -> bool:
        """Execute a scenario."""
        if scenario_id not in self._scenarios:
            return False
        
        scenario = self._scenarios[scenario_id]
        if not scenario.enabled:
            return False
        
        logger.info(f"Executing scenario: {scenario.name}")
        
        for action in scenario.actions:
            handler = self._execution_handlers.get(f"{action.entity_id}.{action.action}")
            if handler:
                await handler(action.entity_id, action.action, action.params)
            else:
                logger.info(f"Action: {action.entity_id}.{action.action}({action.params})")
        
        scenario.usage_count += 1
        scenario.last_used = time.time()
        return True

    def register_handler(self, entity_action: str, handler: Callable):
        """Register execution handler for entity actions."""
        self._execution_handlers[entity_action] = handler

    def _save_to_disk(self, scenario: Scenario):
        """Save scenario to disk."""
        path = self._storage_path / f"{scenario.id}.json"
        with open(path, 'w') as f:
            json.dump({
                "id": scenario.id,
                "name": scenario.name,
                "category": scenario.category.value,
                "actions": [{"entity": a.entity_id, "action": a.action, "params": a.params} for a in scenario.actions],
            }, f, indent=2)

    def get_scenarios(self, category: Optional[ScenarioCategory] = None) -> List[Scenario]:
        """Get all scenarios."""
        if category:
            return [s for s in self._scenarios.values() if s.category == category]
        return list(self._scenarios.values())

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario."""
        if scenario_id in self._scenarios:
            del self._scenarios[scenario_id]
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get scenario statistics."""
        return {
            "total_scenarios": len(self._scenarios),
            "by_category": {c.value: len([s for s in self._scenarios.values() if s.category == c]) for c in ScenarioCategory},
            "total_executions": sum(s.usage_count for s in self._scenarios.values()),
        }


# Global default scenario engine
default_scenarios: Optional[ScenarioEngine] = None


def init_scenario_engine() -> ScenarioEngine:
    """Initialize global scenario engine."""
    global default_scenarios
    default_scenarios = ScenarioEngine()
    return default_scenarios
