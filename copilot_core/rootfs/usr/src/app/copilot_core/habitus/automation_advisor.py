"""Habitus Automation Advisor.

Builds actionable automation suggestions from mined habitus rules and maps
them to core neuron contexts for explainability and routing.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


_NEURON_HINTS = [
    ("motion", "context.presence"),
    ("presence", "context.presence"),
    ("occupancy", "context.presence"),
    ("light", "state.light_level"),
    ("climate", "state.energy_level"),
    ("temperature", "state.energy_level"),
    ("media_player", "context.activity"),
    ("cover", "context.activity"),
]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_entity(expr: str) -> str:
    txt = str(expr or "")
    if ":" in txt:
        _, tail = txt.split(":", 1)
        return tail.strip()
    return txt.strip()


def _extract_domain(expr: str) -> str:
    entity = _extract_entity(expr)
    if "." in entity:
        return entity.split(".", 1)[0]
    return entity.split(":", 1)[0] if ":" in entity else ""


def _neuron_tags(antecedent: str, consequent: str) -> list[str]:
    text = f"{antecedent} {consequent}".lower()
    out: list[str] = []
    for needle, neuron in _NEURON_HINTS:
        if needle in text and neuron not in out:
            out.append(neuron)
    if not out:
        out.append("context.activity")
    return out


@dataclass
class HabitusAutomationSuggestion:
    """DTO for one automation suggestion derived from a habitus rule."""

    suggestion_id: str
    rule_id: str
    zone: str
    antecedent: str
    consequent: str
    confidence: float
    lift: float
    support: float
    score: float
    neurons: list[str]
    priority: str
    automation_payload: dict[str, Any]
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HabitusAutomationAdvisor:
    """Generate/apply automation suggestions from habitus rules."""

    def __init__(self) -> None:
        self._cache: dict[str, HabitusAutomationSuggestion] = {}

    @staticmethod
    def _priority(score: float) -> str:
        if score >= 2.0:
            return "high"
        if score >= 1.0:
            return "medium"
        return "low"

    @staticmethod
    def _stable_id(rule_id: str, antecedent: str, consequent: str) -> str:
        digest = hashlib.sha1(f"{rule_id}|{antecedent}|{consequent}".encode("utf-8")).hexdigest()
        return f"hab_auto_{digest[:12]}"

    def build_suggestions(
        self,
        rules: list[dict[str, Any]],
        *,
        zone: str = "",
        limit: int = 20,
        min_confidence: float = 0.55,
    ) -> list[dict[str, Any]]:
        """Create actionable suggestions from normalized habitus rules."""
        out: list[HabitusAutomationSuggestion] = []
        for rule in rules:
            antecedent = str(rule.get("A") or rule.get("antecedent") or "").strip()
            consequent = str(rule.get("B") or rule.get("consequent") or "").strip()
            if not antecedent or not consequent:
                continue

            confidence = _as_float(rule.get("confidence"), 0.0)
            if confidence < min_confidence:
                continue

            rule_zone = str(rule.get("zone") or "").strip()
            if zone and zone not in rule_zone:
                continue

            lift = _as_float(rule.get("lift"), 0.0)
            support = _as_float(rule.get("support"), 0.0)
            score = round((confidence * max(lift, 1.0)) + support, 3)
            rid = str(rule.get("id") or rule.get("rule_id") or rule.get("pattern_id") or "")
            sid = self._stable_id(rid or antecedent, antecedent, consequent)
            neurons = _neuron_tags(antecedent, consequent)

            ant_entity = _extract_entity(antecedent)
            cons_entity = _extract_entity(consequent)
            ant_domain = _extract_domain(antecedent)
            cons_domain = _extract_domain(consequent)

            payload = {
                "antecedent": antecedent,
                "consequent": consequent,
                "alias": f"Habitus: {ant_entity} -> {cons_entity}"[:120],
                "metadata": {
                    "source": "habitus",
                    "rule_id": rid,
                    "zone": rule_zone,
                    "neurons": neurons,
                    "domains": [d for d in {ant_domain, cons_domain} if d],
                },
            }

            suggestion = HabitusAutomationSuggestion(
                suggestion_id=sid,
                rule_id=rid or sid,
                zone=rule_zone,
                antecedent=antecedent,
                consequent=consequent,
                confidence=round(confidence, 3),
                lift=round(lift, 3),
                support=round(support, 3),
                score=score,
                neurons=neurons,
                priority=self._priority(score),
                automation_payload=payload,
                created_at=time.time(),
            )
            out.append(suggestion)

        out.sort(key=lambda s: (s.priority == "high", s.score, s.confidence), reverse=True)
        out = out[: max(1, min(limit, 100))]
        self._cache = {s.suggestion_id: s for s in out}
        return [s.to_dict() for s in out]

    def get_cached(self, suggestion_id: str) -> dict[str, Any] | None:
        item = self._cache.get(str(suggestion_id or "").strip())
        return item.to_dict() if item else None
