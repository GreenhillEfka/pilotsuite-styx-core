"""Automation Suggestion Engine — Generate HA automations from patterns (v6.0.0).

Analyzes behavioral patterns from Habitus rules, energy schedules, and comfort
data to suggest Home Assistant automations. Generates valid HA automation
YAML.

Lifecycle handling:
- Raw suggestions can be accepted/rejected/snoozed.
- Accepted suggestions become proposals.
- Proposals can be converted into action intents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    snoozed_until: float | None = None


@dataclass
class SuggestionProposal:
    """Concrete action proposal created from an accepted suggestion."""

    proposal_id: str
    suggestion_id: str
    action_type: str
    action_config: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    confidence: float = 0.0
    created_at: str = field(default_factory=_now_iso)
    accepted_at: str | None = None
    executed_at: str | None = None
    status: str = "proposed"  # proposed / ready_to_execute / executed / cancelled
    action_intent_id: str | None = None


@dataclass
class SuggestionActionIntent:
    """Action intent representing the executable form of a proposal.

    This model intentionally carries both the original Slice-7 contract fields
    (`suggestion_id`, `action_type`, `domain`, `service`, `entity_ids`,
    `evidence`, `explanation`, `policy_decision`) and the later internal
    proposal/intents representation (`proposal_id`, `action`, `params`). That
    keeps older contract tests and newer engine code compatible.
    """

    intent_id: str
    suggestion_id: str = ""
    action_type: str = ""
    domain: str = ""
    service: str = ""
    entity_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    explanation: str = ""
    policy_decision: str = ""
    proposal_id: str = ""
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending / ready / executed / failed
    created_at: str = field(default_factory=_now_iso)
    executed_at: str | None = None
    result: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.action and self.action_type:
            self.action = self.action_type
        if not self.action_type and self.action:
            self.action_type = self.action

        action_config = self.params.get("action_config") if isinstance(self.params, dict) else None
        if isinstance(action_config, dict):
            self.domain = self.domain or str(action_config.get("domain", ""))
            self.service = self.service or str(action_config.get("service", ""))
            if not self.entity_ids:
                entity_ids = action_config.get("entity_ids") or action_config.get("entity_id") or []
                if isinstance(entity_ids, str):
                    entity_ids = [entity_ids]
                self.entity_ids = list(entity_ids)

        if not self.explanation and isinstance(self.params, dict):
            self.explanation = str(self.params.get("explanation", "") or "")


class AutomationSuggestionEngine:
    """Generate automation suggestions from PilotSuite data."""

    def __init__(self):
        self._suggestions: dict[str, AutomationSuggestion] = {}
        self._proposals: dict[str, SuggestionProposal] = {}
        self._intents: dict[str, SuggestionActionIntent] = {}
        self._proposal_of_suggestion: dict[str, str] = {}
        self._suggestion_of_proposal: dict[str, str] = {}
        self._counter = 0
        self._proposal_counter = 0
        self._intent_counter = 0
        logger.info("AutomationSuggestionEngine initialized")

    def _next_suggestion_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:04d}"

    def _next_proposal_id(self) -> str:
        self._proposal_counter += 1
        return f"proposal-{self._proposal_counter:04d}"

    def _next_intent_id(self) -> str:
        self._intent_counter += 1
        return f"intent-{self._intent_counter:04d}"

    # ── Suggestion creation --------------------------------------------------
    def suggest_from_schedule(
        self, device_type: str, start_hour: int, end_hour: int, days: str = "weekday"
    ) -> AutomationSuggestion:
        """Generate time-based automation from schedule pattern."""
        sid = self._next_suggestion_id("auto-sched")

        trigger_time = f"{start_hour:02d}:00:00"
        entity_map = {
            "washer": "switch.washing_machine",
            "dryer": "switch.dryer",
            "dishwasher": "switch.dishwasher",
            "ev_charger": "switch.ev_charger",
        }
        entity = entity_map.get(device_type, f"switch.{device_type}")

        weekdays = (
            ["mon", "tue", "wed", "thu", "fri"]
            if days == "weekday"
            else ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        )

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
                    "delay": {"hours": max(0, end_hour - start_hour), "minutes": 0},
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
        sid = self._next_suggestion_id("auto-solar")

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
        sid = self._next_suggestion_id("auto-comfort")

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

        config = factor_config.get(
            factor,
            {
                "sensor": f"sensor.{factor}",
                "name": factor.title(),
                "unit": "",
                "action_name": f"{action_entity} schalten",
            },
        )

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
            title=(
                f"{config['action_name']} bei {config['name']} {'<' if is_below else '>'} "
                f"{threshold}{config['unit']}"
            ),
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
        sid = self._next_suggestion_id("auto-presence")

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

    # ── Query APIs -----------------------------------------------------------
    def get_suggestions(
        self,
        category: str | None = None,
        include_dismissed: bool = False,
        include_accepted: bool = False,
        include_snoozed: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get all suggestions, optionally filtered."""
        results = []
        for s in self._suggestions.values():
            if not include_dismissed and s.dismissed:
                continue
            if not include_accepted and s.accepted:
                continue
            if not include_snoozed and s.snoozed_until is not None:
                continue
            if category and s.category != category:
                continue
            results.append(self._to_dict(s))

        results.sort(key=lambda x: x["confidence"], reverse=True)
        if limit is not None:
            results = results[:max(0, int(limit))]
        return results

    def get_pending(self, limit: int = 20) -> list[dict[str, Any]]:
        """Backward-compatible helper returning non-accepted suggestions."""
        return self.get_suggestions(
            include_dismissed=False,
            include_accepted=False,
            limit=limit,
        )

    # ── Lifecycle transitions ------------------------------------------------
    def accept_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """Mark suggestion accepted and emit lifecycle proposal."""
        proposal = self.propose_suggestion(suggestion_id)
        if not proposal:
            return None

        suggestion = self._suggestions.get(suggestion_id)
        if not suggestion:
            return None
        payload = self._to_dict(suggestion)
        payload["proposal_id"] = proposal["proposal_id"]
        payload["proposal_status"] = proposal["status"]
        return payload

    def dismiss_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """Mark a suggestion as dismissed (user rejected)."""
        s = self._suggestions.get(suggestion_id)
        if s:
            s.dismissed = True
            return self._to_dict(s)
        return None

    def reject_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """Alias for dismiss_suggestion."""
        return self.dismiss_suggestion(suggestion_id)

    def snooze_suggestion(
        self,
        suggestion_id: str,
        minutes: int = 15,
    ) -> dict[str, Any] | None:
        """Snooze suggestion for N minutes."""
        s = self._suggestions.get(suggestion_id)
        if not s:
            return None
        try:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            s.snoozed_until = (now + timedelta(minutes=max(1, int(minutes)))).timestamp()
        except Exception:
            # Always keep behavior simple and permissive on bad args
            pass
        return self._to_dict(s)

    def propose_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """Convert accepted suggestion into a proposal."""
        suggestion = self._suggestions.get(suggestion_id)
        if not suggestion or suggestion.dismissed:
            return None

        existing_proposal_id = self._proposal_of_suggestion.get(suggestion_id)
        if existing_proposal_id:
            existing = self._proposals.get(existing_proposal_id)
            if existing and existing.status != "cancelled":
                return self._proposal_to_dict(existing)

        proposal_id = self._next_proposal_id()
        proposal = SuggestionProposal(
            proposal_id=proposal_id,
            suggestion_id=suggestion_id,
            action_type="create_automation",
            action_config=suggestion.automation_yaml,
            explanation=suggestion.description,
            confidence=suggestion.confidence,
            created_at=_now_iso(),
            accepted_at=_now_iso(),
            status="proposed",
        )

        suggestion.accepted = True

        self._proposals[proposal_id] = proposal
        self._proposal_of_suggestion[suggestion_id] = proposal_id
        self._suggestion_of_proposal[proposal_id] = suggestion_id
        return self._proposal_to_dict(proposal)

    def get_proposals(self, include_executed: bool = False) -> list[dict[str, Any]]:
        """List proposals."""
        proposals = list(self._proposals.values())
        if not include_executed:
            proposals = [p for p in proposals if p.status != "executed"]
        proposals.sort(key=lambda p: p.created_at, reverse=True)
        return [self._proposal_to_dict(p) for p in proposals]

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        """Get proposal by id."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None
        return self._proposal_to_dict(proposal)

    def create_action_intent(self, proposal_id: str) -> dict[str, Any] | None:
        """Create an action intent for a proposal."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None

        # Reuse latest prepared intent if it is still pending
        if proposal.action_intent_id:
            old = self._intents.get(proposal.action_intent_id)
            if old and old.status in {"pending", "ready"}:
                return self._intent_to_dict(old)

        intent_id = self._next_intent_id()
        params = {
            "action_config": dict(proposal.action_config),
            "proposal_id": proposal_id,
            "suggestion_id": proposal.suggestion_id,
            "explanation": proposal.explanation,
        }
        intent = SuggestionActionIntent(
            intent_id=intent_id,
            suggestion_id=proposal.suggestion_id,
            action_type=proposal.action_type,
            explanation=proposal.explanation,
            proposal_id=proposal_id,
            action="create_automation",
            params=params,
            status="pending",
        )

        proposal.action_intent_id = intent_id
        self._intents[intent_id] = intent
        return self._intent_to_dict(intent)

    def execute_proposal(
        self,
        proposal_id: str,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any] | None:
        """Materialize proposal into action intent. No external execution is performed."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None

        intent_dict = self.create_action_intent(proposal_id)
        if not intent_dict:
            return None

        intent = self._intents[intent_dict["intent_id"]]
        if proposal.status == "executed":
            intent_dict["status"] = intent.status
            return intent_dict

        if dry_run:
            intent.status = "ready"
            proposal.status = "ready_to_execute"
        else:
            intent.status = "executed"
            intent.executed_at = _now_iso()
            intent.result = {"ok": True, "message": "Action intent acknowledged"}
            proposal.status = "executed"
            proposal.executed_at = _now_iso()

        return self._intent_to_dict(intent)

    def get_action_intent(self, intent_id: str) -> dict[str, Any] | None:
        intent = self._intents.get(intent_id)
        if not intent:
            return None
        return self._intent_to_dict(intent)

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
            "snoozed_until": s.snoozed_until,
        }

    @staticmethod
    def _proposal_to_dict(p: SuggestionProposal) -> dict[str, Any]:
        return {
            "proposal_id": p.proposal_id,
            "suggestion_id": p.suggestion_id,
            "action_type": p.action_type,
            "action_config": dict(p.action_config),
            "explanation": p.explanation,
            "confidence": p.confidence,
            "created_at": p.created_at,
            "accepted_at": p.accepted_at,
            "executed_at": p.executed_at,
            "status": p.status,
            "action_intent_id": p.action_intent_id,
        }

    @staticmethod
    def _intent_to_dict(i: SuggestionActionIntent) -> dict[str, Any]:
        return {
            "intent_id": i.intent_id,
            "suggestion_id": i.suggestion_id,
            "action_type": i.action_type,
            "domain": i.domain,
            "service": i.service,
            "entity_ids": list(i.entity_ids),
            "evidence": list(i.evidence),
            "explanation": i.explanation,
            "policy_decision": i.policy_decision,
            "proposal_id": i.proposal_id,
            "action": i.action,
            "params": dict(i.params),
            "status": i.status,
            "created_at": i.created_at,
            "executed_at": i.executed_at,
            "result": i.result,
        }
