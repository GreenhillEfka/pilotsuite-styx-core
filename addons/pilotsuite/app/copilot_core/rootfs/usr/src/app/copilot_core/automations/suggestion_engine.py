"""Automation Suggestion Engine — Generate HA automations from patterns (v5.9.0).

Analyzes behavioral patterns from Habitus rules, energy schedules, and comfort
data to suggest Home Assistant automations. Generates valid HA automation YAML.

Supported suggestion types:
- Time-based: "Every weekday at 07:00, turn on kitchen lights"
- Energy-based: "When solar surplus > 5kWh, start dishwasher"
- Comfort-based: "When CO2 > 1000ppm, turn on ventilation"
- Presence-based: "When nobody home for 30 min, turn off lights"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AutomationSuggestion:
    """A suggested HA automation."""

    id: str
    title: str
    description: str
    category: str  # time, energy, comfort, presence
    confidence: float  # 0-1
    estimated_savings_eur: float | None = None
    automation_yaml: dict[str, Any] = field(default_factory=dict)
    source_pattern: str | None = None  # Which pattern triggered this
    accepted: bool = False
    dismissed: bool = False


class AutomationSuggestionEngine:
    """Generate automation suggestions from PilotSuite data."""

    def __init__(self):
        self._suggestions: dict[str, AutomationSuggestion] = {}
        self._counter = 0
        logger.info("AutomationSuggestionEngine initialized")

    def suggest_from_schedule(
        self, device_type: str, start_hour: int, end_hour: int, days: str = "weekday"
    ) -> AutomationSuggestion:
        """Generate time-based automation from schedule pattern."""
        self._counter += 1
        sid = f"auto-sched-{self._counter:04d}"

        trigger_time = f"{start_hour:02d}:00:00"
        action_time = f"{end_hour:02d}:00:00"

        weekdays = (
            ["mon", "tue", "wed", "thu", "fri"]
            if days == "weekday"
            else ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        )

        entity_map = {
            "washer": "switch.washing_machine",
            "dryer": "switch.dryer",
            "dishwasher": "switch.dishwasher",
            "ev_charger": "switch.ev_charger",
        }
        entity = entity_map.get(device_type, f"switch.{device_type}")

        device_names = {
            "washer": "Waschmaschine",
            "dryer": "Trockner",
            "dishwasher": "Geschirrspueler",
            "ev_charger": "E-Auto Laden",
        }
        name = device_names.get(device_type, device_type.title())

        automation = {
            "alias": f"PilotSuite: {name} automatisch starten",
            "description": f"Startet {name} zum optimalen Zeitpunkt ({start_hour}:00-{end_hour}:00)",
            "trigger": [
                {
                    "platform": "time",
                    "at": trigger_time,
                }
            ],
            "condition": [
                {
                    "condition": "time",
                    "weekday": weekdays,
                }
            ],
            "action": [
                {
                    "service": "switch.turn_on",
                    "target": {"entity_id": entity},
                },
                {
                    "delay": {"hours": end_hour - start_hour, "minutes": 0},
                },
                {
                    "service": "switch.turn_off",
                    "target": {"entity_id": entity},
                },
            ],
            "mode": "single",
        }

        suggestion = AutomationSuggestion(
            id=sid,
            title=f"{name} automatisch um {start_hour}:00 starten",
            description=(
                f"Basierend auf dem Energiezeitplan: {name} laeuft optimal "
                f"zwischen {start_hour}:00 und {end_hour}:00 ({days})."
            ),
            category="time",
            confidence=0.8,
            estimated_savings_eur=0.15,
            automation_yaml=automation,
            source_pattern=f"schedule:{device_type}:{start_hour}-{end_hour}",
        )

        self._suggestions[sid] = suggestion
        return suggestion

    def suggest_from_solar(
        self, device_type: str, surplus_threshold_kwh: float = 5.0
    ) -> AutomationSuggestion:
        """Generate energy-based automation from solar surplus pattern."""
        self._counter += 1
        sid = f"auto-solar-{self._counter:04d}"

        entity_map = {
            "washer": "switch.washing_machine",
            "dryer": "switch.dryer",
            "dishwasher": "switch.dishwasher",
            "ev_charger": "switch.ev_charger",
        }
        entity = entity_map.get(device_type, f"switch.{device_type}")
        device_names = {
            "washer": "Waschmaschine",
            "dryer": "Trockner",
            "dishwasher": "Geschirrspueler",
            "ev_charger": "E-Auto Laden",
        }
        name = device_names.get(device_type, device_type.title())

        automation = {
            "alias": f"PilotSuite: {name} bei Solarueberschuss",
            "description": f"Startet {name} wenn Solarueberschuss > {surplus_threshold_kwh} kWh",
            "trigger": [
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.pilotsuite_energy_production",
                    "above": surplus_threshold_kwh,
                }
            ],
            "condition": [
                {
                    "condition": "state",
                    "entity_id": entity,
                    "state": "off",
                }
            ],
            "action": [
                {
                    "service": "switch.turn_on",
                    "target": {"entity_id": entity},
                }
            ],
            "mode": "single",
        }

        suggestion = AutomationSuggestion(
            id=sid,
            title=f"{name} bei Solarueberschuss starten",
            description=(
                f"Wenn die Solarproduktion {surplus_threshold_kwh} kWh uebersteigt, "
                f"wird {name} automatisch gestartet."
            ),
            category="energy",
            confidence=0.75,
            estimated_savings_eur=0.25,
            automation_yaml=automation,
            source_pattern=f"solar:{device_type}:>{surplus_threshold_kwh}kwh",
        )

        self._suggestions[sid] = suggestion
        return suggestion

    def suggest_from_comfort(
        self,
        factor: str,
        threshold: float,
        action_entity: str,
        action_service: str = "switch.turn_on",
    ) -> AutomationSuggestion:
        """Generate comfort-based automation."""
        self._counter += 1
        sid = f"auto-comfort-{self._counter:04d}"

        factor_config = {
            "co2": {
                "sensor": "sensor.co2",
                "name": "CO2-Wert",
                "unit": "ppm",
                "action_name": "Lueftung einschalten",
            },
            "temperature_high": {
                "sensor": "sensor.temperature",
                "name": "Temperatur",
                "unit": "C",
                "action_name": "Klimaanlage einschalten",
            },
            "temperature_low": {
                "sensor": "sensor.temperature",
                "name": "Temperatur",
                "unit": "C",
                "action_name": "Heizung erhoehen",
            },
            "humidity_high": {
                "sensor": "sensor.humidity",
                "name": "Luftfeuchtigkeit",
                "unit": "%",
                "action_name": "Entfeuchter einschalten",
            },
        }

        config = factor_config.get(factor, {
            "sensor": f"sensor.{factor}",
            "name": factor.title(),
            "unit": "",
            "action_name": f"{action_entity} schalten",
        })

        is_below = factor in ("temperature_low",)

        trigger = {
            "platform": "numeric_state",
            "entity_id": config["sensor"],
        }
        if is_below:
            trigger["below"] = threshold
        else:
            trigger["above"] = threshold

        automation = {
            "alias": f"PilotSuite: {config['action_name']}",
            "description": (
                f"Automatisch {config['action_name']} wenn "
                f"{config['name']} {'unter' if is_below else 'ueber'} "
                f"{threshold} {config['unit']}"
            ),
            "trigger": [trigger],
            "action": [
                {
                    "service": action_service,
                    "target": {"entity_id": action_entity},
                }
            ],
            "mode": "single",
        }

        suggestion = AutomationSuggestion(
            id=sid,
            title=f"{config['action_name']} bei {config['name']} {'<' if is_below else '>'} {threshold}{config['unit']}",
            description=automation["description"],
            category="comfort",
            confidence=0.7,
            automation_yaml=automation,
            source_pattern=f"comfort:{factor}:{'<' if is_below else '>'}{threshold}",
        )

        self._suggestions[sid] = suggestion
        return suggestion

    def suggest_from_presence(
        self,
        away_minutes: int = 30,
        entities: list[str] | None = None,
    ) -> AutomationSuggestion:
        """Generate presence-based automation (away mode)."""
        self._counter += 1
        sid = f"auto-presence-{self._counter:04d}"

        target_entities = entities or [
            "light.living_room", "light.kitchen", "light.bedroom",
        ]

        automation = {
            "alias": "PilotSuite: Alles aus bei Abwesenheit",
            "description": (
                f"Schaltet Lichter aus wenn niemand fuer {away_minutes} Min. zu Hause ist"
            ),
            "trigger": [
                {
                    "platform": "state",
                    "entity_id": "group.all_persons",
                    "to": "not_home",
                    "for": {"minutes": away_minutes},
                }
            ],
            "action": [
                {
                    "service": "light.turn_off",
                    "target": {"entity_id": target_entities},
                }
            ],
            "mode": "single",
        }

        suggestion = AutomationSuggestion(
            id=sid,
            title=f"Lichter aus nach {away_minutes} Min. Abwesenheit",
            description=automation["description"],
            category="presence",
            confidence=0.85,
            estimated_savings_eur=0.10,
            automation_yaml=automation,
            source_pattern=f"presence:away:{away_minutes}min",
        )

        self._suggestions[sid] = suggestion
        return suggestion

    def get_suggestions(
        self, category: str | None = None, include_dismissed: bool = False,
    ) -> list[dict[str, Any]]:
        """Get all suggestions, optionally filtered."""
        results = []
        for s in self._suggestions.values():
            if not include_dismissed and s.dismissed:
                continue
            if category and s.category != category:
                continue
            results.append(self._to_dict(s))

        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results

    def accept_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """Mark a suggestion as accepted (user approved)."""
        s = self._suggestions.get(suggestion_id)
        if s:
            s.accepted = True
            return self._to_dict(s)
        return None

    def dismiss_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """Mark a suggestion as dismissed (user rejected)."""
        s = self._suggestions.get(suggestion_id)
        if s:
            s.dismissed = True
            return self._to_dict(s)
        return None

    def get_suggestion_yaml(self, suggestion_id: str) -> dict[str, Any] | None:
        """Get the raw automation YAML for a suggestion."""
        s = self._suggestions.get(suggestion_id)
        if s:
            return s.automation_yaml
        return None

    @staticmethod
    def _to_dict(s: AutomationSuggestion) -> dict[str, Any]:
        return {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "category": s.category,
            "confidence": s.confidence,
            "estimated_savings_eur": s.estimated_savings_eur,
            "automation_yaml": s.automation_yaml,
            "source_pattern": s.source_pattern,
            "accepted": s.accepted,
            "dismissed": s.dismissed,
        }
