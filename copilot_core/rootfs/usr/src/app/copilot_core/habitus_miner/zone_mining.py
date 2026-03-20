"""Zone-based A→B rule mining for Habitus Miner.

Extends the base mining with zone-awareness:
- Filter events by zone (only mine patterns for entities in the same zone)
- Apply zone governance rules (confirmation, safety-critical entities)
- Turn mined rules into first-layer automation proposals with explainable confidence

Architecture:
    Events → Zone Filter → Zone-Scoped Mining → Governance Check → Proposals

See: docs/HABITUS_PHILOSOPHY.md
"""
from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime
from typing import Any, Optional

from .model import NormEvent, Rule, MiningConfig, EventStreamType
from .mining import mine_ab_rules
from copilot_core.homeassistant.habitus_zones import infer_module_id_for_action

_LOGGER = logging.getLogger(__name__)

_ACTIVE_STATES = {"on", "open", "opening", "playing", "active", "home", "occupied", "detected"}
_INACTIVE_STATES = {"off", "closed", "closing", "paused", "idle", "standby", "not_home", "clear", "unoccupied"}
_PRESENCE_ENTITY_TOKENS = (
    "presence", "occupancy", "occupied", "motion", "bewegung", "praesenz", "präsenz", "person", "pir", "mmwave",
)
_AMBIENT_LIGHT_STATES = {"very_dark", "dark", "dim", "bright", "very_bright"}
_TEMPERATURE_STATES = {"cold", "cool", "comfortable", "warm", "hot"}
_HUMIDITY_STATES = {"dry", "normal", "humid", "very_humid"}


class ZoneMiningConfig:
    """Configuration for zone-based mining."""

    def __init__(
        self,
        zone_id: str,
        min_events: int = 10,
        confidence_threshold: float = 0.7,
        lift_threshold: float = 1.5,
        requires_confirmation: bool = True,
        safety_critical_entities: Optional[set[str]] = None,
    ):
        self.zone_id = zone_id
        self.min_events = min_events
        self.confidence_threshold = confidence_threshold
        self.lift_threshold = lift_threshold
        self.requires_confirmation = requires_confirmation
        self.safety_critical_entities = safety_critical_entities or set()


class ZoneMiningResult:
    """Result of zone-based mining."""

    def __init__(self, zone_id: str):
        self.zone_id = zone_id
        self.rules: list[Rule] = []
        self.filtered_rules: list[Rule] = []
        self.safety_blocked: list[dict[str, Any]] = []
        self.stats: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "rules_count": len(self.rules),
            "filtered_count": len(self.filtered_rules),
            "safety_blocked_count": len(self.safety_blocked),
            "stats": self.stats,
            "top_rules": [
                {
                    "A": r.A,
                    "B": r.B,
                    "confidence": round(r.confidence, 3),
                    "lift": round(r.lift, 2),
                    "score": round(r.score(), 3),
                }
                for r in self.filtered_rules[:5]
            ],
        }


class ZoneBasedMiner:
    """Zone-aware pattern miner.

    Integrates with TagZoneIntegration to:
    1. Filter events by zone membership
    2. Apply zone-specific governance
    3. Generate zone-scoped suggestions and automation proposals

    Usage:
        miner = ZoneBasedMiner(tag_zone_integration)
        results = miner.mine_all_zones(events, configs)
    """

    def __init__(
        self,
        tag_zone_integration: Any,  # TagZoneIntegration from tagging/
        base_config: Optional[MiningConfig] = None,
    ):
        self.tag_zone = tag_zone_integration
        self.base_config = base_config or MiningConfig()
        self._zone_configs: dict[str, ZoneMiningConfig] = {}

    def set_zone_config(self, zone_id: str, config: ZoneMiningConfig) -> None:
        """Set mining configuration for a zone."""
        self._zone_configs[zone_id] = config
        _LOGGER.info("ZoneBasedMiner: Set config for zone %s", zone_id)

    def get_zone_config(self, zone_id: str) -> ZoneMiningConfig:
        """Get mining configuration for a zone (returns default if not set)."""
        return self._zone_configs.get(zone_id, ZoneMiningConfig(zone_id))

    def filter_events_by_zone(
        self,
        events: EventStreamType,
        zone_id: str,
    ) -> EventStreamType:
        """Filter events to only include entities in the specified zone."""
        zone_entities = self.tag_zone.get_entities_for_zone(zone_id)
        if not zone_entities:
            return []

        zone_entity_set = set(zone_entities)
        filtered = [e for e in events if e.entity_id in zone_entity_set]

        _LOGGER.debug(
            "ZoneBasedMiner: Filtered %d events to %d for zone %s (%d entities)",
            len(events), len(filtered), zone_id, len(zone_entities)
        )

        return filtered

    def mine_zone(
        self,
        events: EventStreamType,
        zone_id: str,
        zone_config: Optional[ZoneMiningConfig] = None,
    ) -> ZoneMiningResult:
        """Mine rules for a specific zone."""
        config = zone_config or self.get_zone_config(zone_id)
        result = ZoneMiningResult(zone_id)

        zone_events = self.filter_events_by_zone(events, zone_id)

        if len(zone_events) < config.min_events:
            _LOGGER.info(
                "ZoneBasedMiner: Zone %s has only %d events (min: %d), skipping",
                zone_id, len(zone_events), config.min_events
            )
            result.stats = {
                "events": len(zone_events),
                "skipped": True,
                "reason": "insufficient_events",
            }
            return result

        result.rules = mine_ab_rules(zone_events, self.base_config)
        result.filtered_rules = []

        for rule in result.rules:
            if rule.confidence < config.confidence_threshold:
                continue
            if rule.lift < config.lift_threshold:
                continue

            a_entity = rule.A.split(":")[0] if ":" in rule.A else rule.A
            b_entity = rule.B.split(":")[0] if ":" in rule.B else rule.B

            a_critical = a_entity in config.safety_critical_entities
            b_critical = b_entity in config.safety_critical_entities

            if a_critical or b_critical:
                result.safety_blocked.append({
                    "rule": f"{rule.A} → {rule.B}",
                    "confidence": round(rule.confidence, 3),
                    "lift": round(rule.lift, 2),
                    "blocked_by": "safety_critical",
                    "entities": [e for e in [a_entity, b_entity] if e in config.safety_critical_entities],
                })
                continue

            result.filtered_rules.append(rule)

        result.stats = {
            "events": len(zone_events),
            "raw_rules": len(result.rules),
            "filtered_rules": len(result.filtered_rules),
            "safety_blocked": len(result.safety_blocked),
            "confidence_threshold": config.confidence_threshold,
            "lift_threshold": config.lift_threshold,
            "requires_confirmation": config.requires_confirmation,
        }

        _LOGGER.info(
            "ZoneBasedMiner: Zone %s mined %d rules -> %d filtered (%d safety-blocked)",
            zone_id, len(result.rules), len(result.filtered_rules), len(result.safety_blocked)
        )

        return result

    def mine_all_zones(
        self,
        events: EventStreamType,
        zone_configs: Optional[dict[str, ZoneMiningConfig]] = None,
    ) -> dict[str, ZoneMiningResult]:
        """Mine rules for all zones."""
        results = {}
        all_zones = self.tag_zone.get_all_zones()

        if not all_zones:
            _LOGGER.warning("ZoneBasedMiner: No zones found")
            return results

        _LOGGER.info(
            "ZoneBasedMiner: Mining %d zones with %d total events",
            len(all_zones), len(events)
        )

        for zone_id in all_zones:
            config = (zone_configs or {}).get(zone_id, self.get_zone_config(zone_id))
            results[zone_id] = self.mine_zone(events, zone_id, config)

        return results

    def get_top_suggestions(
        self,
        results: dict[str, ZoneMiningResult],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get top raw rule suggestions across all zones."""
        all_rules = []

        for zone_id, result in results.items():
            config = self.get_zone_config(zone_id)

            for rule in result.filtered_rules:
                all_rules.append({
                    "zone_id": zone_id,
                    "A": rule.A,
                    "B": rule.B,
                    "confidence": rule.confidence,
                    "lift": rule.lift,
                    "score": rule.score(),
                    "requires_confirmation": config.requires_confirmation,
                    "safety_critical": False,
                })

        all_rules.sort(key=lambda x: x["score"], reverse=True)
        return all_rules[:limit]

    def _split_event_key(self, key: str) -> tuple[str, str]:
        if ":" not in key:
            return key, ""
        entity_id, transition = key.rsplit(":", 1)
        return entity_id, transition.lstrip(":").lower()

    def _is_presence_entity(self, entity_id: str, domain: str) -> bool:
        entity_lower = entity_id.lower()
        return domain in {"person", "device_tracker"} or any(token in entity_lower for token in _PRESENCE_ENTITY_TOKENS)

    def _classify_event(self, key: str) -> dict[str, Any]:
        entity_id, state = self._split_event_key(key)
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        entity_lower = entity_id.lower()

        role = "other"
        semantic = "other"
        active_state = state in _ACTIVE_STATES
        inactive_state = state in _INACTIVE_STATES
        sensor_type = None

        if self._is_presence_entity(entity_id, domain):
            role = "presence"
            if active_state:
                semantic = "presence_active"
            elif inactive_state:
                semantic = "presence_inactive"
            else:
                semantic = "presence_signal"
        elif domain == "media_player":
            role = "media"
            if state in {"playing", "buffering", "on"}:
                semantic = "media_active"
            elif state in {"paused", "idle", "off", "standby"}:
                semantic = "media_inactive"
            else:
                semantic = "media_signal"
        elif domain in {"sensor", "binary_sensor"}:
            role = "sensor"
            if state in _AMBIENT_LIGHT_STATES or any(token in entity_lower for token in ("illuminance", "brightness", "lux", "light_level")):
                sensor_type = "ambient_light"
                semantic = f"sensor_{state}" if state else "sensor_ambient_light"
            elif state in _TEMPERATURE_STATES or any(token in entity_lower for token in ("temperature", "temp")):
                sensor_type = "temperature"
                semantic = f"sensor_{state}" if state else "sensor_temperature"
            elif state in _HUMIDITY_STATES or any(token in entity_lower for token in ("humidity", "feuchtigkeit")):
                sensor_type = "humidity"
                semantic = f"sensor_{state}" if state else "sensor_humidity"
            else:
                semantic = "sensor_signal"
        elif domain in {"light", "switch", "fan", "cover", "climate", "input_boolean"}:
            role = "actuator"
            semantic = f"{domain}_{state}" if state else domain

        return {
            "key": key,
            "entity_id": entity_id,
            "state": state,
            "domain": domain,
            "role": role,
            "semantic": semantic,
            "sensor_type": sensor_type,
            "is_active": active_state,
            "is_inactive": inactive_state,
            "label": f"{entity_id} → {state}" if state else entity_id,
        }

    def _lift_score(self, lift: float) -> float:
        if lift <= 1.0:
            return 0.0
        return min(1.0, math.log(lift, 4))

    def _support_score(self, hits: int) -> float:
        if hits <= 0:
            return 0.0
        return min(1.0, math.log1p(hits) / math.log(21))

    def _calculate_explainable_confidence(self, rule: Rule) -> tuple[float, dict[str, float]]:
        lift_score = self._lift_score(rule.lift)
        support_score = self._support_score(rule.nAB)
        confidence = (
            0.5 * rule.confidence_lb
            + 0.2 * rule.confidence
            + 0.15 * lift_score
            + 0.15 * support_score
        )
        confidence = max(0.0, min(1.0, confidence))
        breakdown = {
            "stable_confidence": round(rule.confidence_lb, 3),
            "observed_success_rate": round(rule.confidence, 3),
            "lift_score": round(lift_score, 3),
            "support_score": round(support_score, 3),
        }
        return round(confidence, 3), breakdown

    def _confidence_label(self, confidence: float) -> str:
        if confidence >= 0.85:
            return "very_high"
        if confidence >= 0.7:
            return "high"
        if confidence >= 0.55:
            return "medium"
        return "low"

    def _infer_action_service(self, event: dict[str, Any]) -> str:
        domain = event["domain"]
        state = event["state"]

        if domain in {"light", "switch", "fan", "input_boolean"}:
            return "turn_on" if event["is_active"] else "turn_off"
        if domain == "media_player":
            if state in {"playing", "buffering", "on"}:
                return "media_play"
            if state == "paused":
                return "media_pause"
            return "media_stop"
        if domain == "cover":
            if state in {"open", "opening", "on"}:
                return "open_cover"
            return "close_cover"
        if domain == "climate":
            return "set_hvac_mode"
        return "set_state"

    def _proposal_type(self, antecedent: dict[str, Any], consequent: dict[str, Any]) -> str | None:
        a_semantic = antecedent["semantic"]
        b_domain = consequent["domain"]

        if a_semantic == "presence_active":
            if b_domain in {"light", "switch"} and consequent["is_active"]:
                return "presence_lights_on"
            if b_domain == "media_player" and consequent["state"] in {"playing", "buffering", "on"}:
                return "presence_media_resume"
            if b_domain == "cover" and consequent["state"] in {"open", "opening"}:
                return "presence_opens_cover"

        if a_semantic == "presence_inactive":
            if b_domain in {"light", "switch", "fan", "input_boolean"} and consequent["is_inactive"]:
                return "absence_turns_devices_off"
            if b_domain == "media_player" and consequent["state"] in {"paused", "idle", "off", "standby"}:
                return "absence_quiets_media"
            if b_domain == "cover" and consequent["state"] in {"closed", "closing"}:
                return "absence_closes_cover"

        if a_semantic == "media_active" and b_domain in {"light", "cover", "climate"}:
            return "media_sets_ambience"
        if a_semantic == "media_inactive" and b_domain in {"light", "cover"}:
            return "media_releases_ambience"

        if antecedent["role"] == "sensor" and consequent["domain"] in {"light", "climate", "fan", "cover"}:
            return "sensor_driven_adjustment"

        return None

    def _proposal_title(self, zone_id: str, proposal_type: str, antecedent: dict[str, Any], consequent: dict[str, Any]) -> str:
        zone = zone_id.replace("zone:", "")
        titles = {
            "presence_lights_on": f"{zone}: Präsenz schaltet Licht automatisch ein",
            "presence_media_resume": f"{zone}: Präsenz startet Medien automatisch",
            "presence_opens_cover": f"{zone}: Präsenz öffnet den Raum",
            "absence_turns_devices_off": f"{zone}: Abwesenheit schaltet Geräte aus",
            "absence_quiets_media": f"{zone}: Abwesenheit stoppt Medien",
            "absence_closes_cover": f"{zone}: Abwesenheit schließt Beschattung",
            "media_sets_ambience": f"{zone}: Medien setzen die Raumstimmung",
            "media_releases_ambience": f"{zone}: Medien-Ende löst Raumstimmung wieder",
            "sensor_driven_adjustment": f"{zone}: Sensorwert löst Raum-Anpassung aus",
        }
        return titles.get(proposal_type, f"{zone}: {antecedent['entity_id']} beeinflusst {consequent['entity_id']}")

    def _proposal_summary(self, proposal_type: str, antecedent: dict[str, Any], consequent: dict[str, Any]) -> str:
        templates = {
            "presence_lights_on": "Wenn Präsenz erkannt wird, folgt typischerweise Licht oder ein Schalter im selben Raum.",
            "presence_media_resume": "Wenn Präsenz erkannt wird, startet im selben Raum häufig die Medienwiedergabe.",
            "presence_opens_cover": "Wenn jemand ankommt, wird die Beschattung im Raum häufig geöffnet.",
            "absence_turns_devices_off": "Wenn Präsenz verschwindet, gehen Geräte im Raum häufig wieder aus.",
            "absence_quiets_media": "Wenn niemand mehr da ist, wird Medienwiedergabe häufig pausiert oder gestoppt.",
            "absence_closes_cover": "Wenn der Raum leer wird, schließt sich häufig die Beschattung.",
            "media_sets_ambience": "Wenn Medien starten, passen sich Licht, Beschattung oder Klima oft an.",
            "media_releases_ambience": "Wenn Medien enden, wird die Raumstimmung häufig zurückgenommen.",
            "sensor_driven_adjustment": "Ein beobachteter Sensorzustand scheint zuverlässig eine Raum-Anpassung auszulösen.",
        }
        return templates.get(proposal_type, f"{antecedent['label']} führt oft zu {consequent['label']}.")

    def _serialize_examples(self, rule: Rule) -> list[dict[str, Any]]:
        if not rule.evidence or not rule.evidence.hit_examples:
            return []

        examples = []
        for t_a, t_b, latency_ms in rule.evidence.hit_examples[:3]:
            examples.append({
                "triggered_at": datetime.utcfromtimestamp(t_a / 1000).isoformat() + "Z",
                "followed_at": datetime.utcfromtimestamp(t_b / 1000).isoformat() + "Z",
                "delay_sec": round(latency_ms / 1000, 1),
            })
        return examples

    def _typical_delay(self, rule: Rule) -> float:
        if rule.evidence and len(rule.evidence.latency_quantiles) >= 2:
            return round(rule.evidence.latency_quantiles[1], 1)
        return round(rule.dt_sec / 2, 1)

    def _proposal_id(self, zone_id: str, proposal_type: str, rule: Rule) -> str:
        digest = hashlib.sha1(f"{zone_id}|{proposal_type}|{rule.A}|{rule.B}|{rule.dt_sec}".encode("utf-8")).hexdigest()
        return f"proposal:{digest[:12]}"

    def build_zone_proposals(
        self,
        results: dict[str, ZoneMiningResult],
        *,
        limit: int = 10,
        min_confidence: float = 0.55,
        zone_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build automation proposals from mined zone rules.

        This is the first proposal layer for habitus zones: suggestions are
        generated from observed correlations, with a transparent confidence
        breakdown, instead of from hardcoded preset names.
        """
        best_candidates: dict[tuple[str, str, str, str], dict[str, Any]] = {}

        for current_zone_id, result in results.items():
            if zone_id and current_zone_id != zone_id:
                continue

            config = self.get_zone_config(current_zone_id)
            for rule in result.filtered_rules:
                antecedent = self._classify_event(rule.A)
                consequent = self._classify_event(rule.B)
                proposal_type = self._proposal_type(antecedent, consequent)
                if not proposal_type:
                    continue

                explainable_confidence, breakdown = self._calculate_explainable_confidence(rule)
                if explainable_confidence < min_confidence:
                    continue

                signature = (current_zone_id, proposal_type, rule.A, rule.B)
                existing = best_candidates.get(signature)
                candidate = {
                    "zone_id": current_zone_id,
                    "rule": rule,
                    "proposal_type": proposal_type,
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "confidence": explainable_confidence,
                    "confidence_breakdown": breakdown,
                    "requires_confirmation": config.requires_confirmation,
                }
                if existing is None or candidate["confidence"] > existing["confidence"] or rule.score() > existing["rule"].score():
                    best_candidates[signature] = candidate

        proposals = []
        for candidate in best_candidates.values():
            rule = candidate["rule"]
            antecedent = candidate["antecedent"]
            consequent = candidate["consequent"]
            typical_delay_s = self._typical_delay(rule)

            action_payload = {
                **consequent,
                "suggested_service": self._infer_action_service(consequent),
            }
            module_id = infer_module_id_for_action(action_payload)

            proposal = {
                "proposal_id": self._proposal_id(candidate["zone_id"], candidate["proposal_type"], rule),
                "zone_id": candidate["zone_id"],
                "type": candidate["proposal_type"],
                "module_id": module_id,
                "title": self._proposal_title(candidate["zone_id"], candidate["proposal_type"], antecedent, consequent),
                "summary": self._proposal_summary(candidate["proposal_type"], antecedent, consequent),
                "confidence": candidate["confidence"],
                "confidence_label": self._confidence_label(candidate["confidence"]),
                "score": round(rule.score(), 3),
                "requires_confirmation": candidate["requires_confirmation"],
                "trigger": {
                    **antecedent,
                    "observed_trials": rule.nA,
                },
                "action": {
                    **action_payload,
                    "module_id": module_id,
                },
                "automation_preview": {
                    "trigger": {
                        "platform": "state",
                        "entity_id": antecedent["entity_id"],
                        "to": antecedent["state"],
                    },
                    "action": {
                        "domain": consequent["domain"],
                        "service": self._infer_action_service(consequent),
                        "target": {"entity_id": consequent["entity_id"]},
                        "expected_state": consequent["state"],
                    },
                    "delay_sec": typical_delay_s,
                },
                "confidence_breakdown": candidate["confidence_breakdown"],
                "evidence": {
                    "observed_hits": rule.nAB,
                    "observed_trials": rule.nA,
                    "baseline_probability": round(rule.baseline_p_b, 3),
                    "lift": round(rule.lift, 2),
                    "window_sec": rule.dt_sec,
                    "typical_delay_sec": typical_delay_s,
                    "observation_period_days": rule.observation_period_days,
                    "examples": self._serialize_examples(rule),
                },
            }
            proposal["explanation"] = self.explain_proposal(proposal)
            proposals.append(proposal)

        proposals.sort(key=lambda item: (item["confidence"], item["score"]), reverse=True)
        return proposals[:limit]

    def explain_suggestion(self, suggestion: dict[str, Any]) -> str:
        """Generate human-readable explanation for a raw suggestion."""
        zone = suggestion["zone_id"].replace("zone:", "")
        a_entity, a_state = suggestion["A"].rsplit(":", 1) if ":" in suggestion["A"] else (suggestion["A"], "?")
        b_entity, b_state = suggestion["B"].rsplit(":", 1) if ":" in suggestion["B"] else (suggestion["B"], "?")

        explanation = (
            f"Im Zone '{zone}': Wenn {a_entity} → {a_state}, "
            f"dann meistens {b_entity} → {b_state} "
            f"(Konfidenz: {suggestion['confidence']:.0%}, Lift: {suggestion['lift']:.1f}x)"
        )

        if suggestion["requires_confirmation"]:
            explanation += " [Bestätigung erforderlich]"

        return explanation

    def explain_proposal(self, proposal: dict[str, Any]) -> str:
        """Generate a human-readable explanation for a proposal."""
        zone = proposal["zone_id"].replace("zone:", "")
        trigger = proposal["trigger"]
        action = proposal["action"]
        evidence = proposal["evidence"]

        explanation = (
            f"In Zone '{zone}' wurde beobachtet: Wenn {trigger['entity_id']} auf "
            f"'{trigger['state']}' wechselt, folgt {action['entity_id']} meist nach "
            f"ca. {evidence['typical_delay_sec']}s mit Zustand '{action['state']}'. "
            f"Das Muster trat {evidence['observed_hits']} mal in {evidence['observed_trials']} Beobachtungen auf "
            f"(erklärbare Konfidenz {proposal['confidence']:.0%}, Lift {evidence['lift']:.1f}x)."
        )

        if proposal.get("requires_confirmation"):
            explanation += " Vorschlag bleibt bestätigungspflichtig."

        return explanation

    def export_results(
        self,
        results: dict[str, ZoneMiningResult],
        *,
        proposal_limit: int = 10,
        proposal_min_confidence: float = 0.55,
    ) -> dict[str, Any]:
        """Export all results for API/UI."""
        proposals = self.build_zone_proposals(
            results,
            limit=proposal_limit,
            min_confidence=proposal_min_confidence,
        )
        return {
            "zones": {zid: r.to_dict() for zid, r in results.items()},
            "top_suggestions": self.get_top_suggestions(results),
            "proposals": proposals,
            "summary": {
                "total_zones": len(results),
                "total_rules": sum(len(r.rules) for r in results.values()),
                "total_filtered": sum(len(r.filtered_rules) for r in results.values()),
                "total_safety_blocked": sum(len(r.safety_blocked) for r in results.values()),
                "total_proposals": len(proposals),
            },
        }
