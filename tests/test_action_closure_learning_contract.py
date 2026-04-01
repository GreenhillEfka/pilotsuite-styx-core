"""Contract coverage for Slice 19 closure-driven learning and prioritization."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.action_closure import get_action_closure_store  # noqa: E402
from copilot_core.habitus_miner.model import MiningConfig, Rule  # noqa: E402
from copilot_core.habitus_miner.zone_mining import ZoneBasedMiner, ZoneMiningResult  # noqa: E402
from copilot_core.multizone.coordination_engine import MultiZoneCoordinationEngine  # noqa: E402
from copilot_core.predictive.automation_engine import (  # noqa: E402
    BehavioralPattern,
    PatternType,
    PredictionConfidence,
    PredictiveAutomationEngine,
)


def setup_function() -> None:
    get_action_closure_store().clear()


class _StubTagZoneIntegration:
    def get_all_zones(self):
        return ["zone:living"]

    def get_entities_for_zone(self, zone_id: str):
        if zone_id == "zone:living":
            return [
                "binary_sensor.arrival",
                "binary_sensor.couch_presence",
                "light.sofa",
                "light.corner",
            ]
        return []


def _seed_closure(
    *,
    source: str,
    zone_id: str,
    module_id: str,
    metadata: dict | None = None,
    service_call: dict | None = None,
    subject_type: str | None = None,
    outcome: str,
) -> None:
    store = get_action_closure_store()
    closure = store.upsert(
        source=source,
        proposal_id="proposal:test",
        action_id=f"action:{source}:{outcome}",
        zone_id=zone_id,
        module_id=module_id,
        metadata=metadata,
        service_call=service_call,
        subject_type=subject_type,
    )
    store.record_execution(
        closure["closure_id"],
        outcome=outcome,
        runtime_source="test.runtime",
    )


def test_predictive_proposals_use_closure_learning_bias() -> None:
    now_hour = datetime.now(timezone.utc).hour
    engine = PredictiveAutomationEngine()
    engine._patterns["pattern_positive"] = BehavioralPattern(
        pattern_id="pattern_positive",
        pattern_type=PatternType.TIME_BASED,
        zone_id="zone:living",
        module_id="light",
        entity_id="light.sofa",
        trigger_conditions={"hour": now_hour, "hour_tolerance": 1},
        typical_action={"domain": "light", "service": "turn_on", "entity_id": "light.sofa", "state": "on"},
        occurrence_count=6,
        confidence=PredictionConfidence.HIGH,
    )
    engine._patterns["pattern_negative"] = BehavioralPattern(
        pattern_id="pattern_negative",
        pattern_type=PatternType.TIME_BASED,
        zone_id="zone:living",
        module_id="light",
        entity_id="light.corner",
        trigger_conditions={"hour": now_hour, "hour_tolerance": 1},
        typical_action={"domain": "light", "service": "turn_on", "entity_id": "light.corner", "state": "on"},
        occurrence_count=6,
        confidence=PredictionConfidence.HIGH,
    )

    _seed_closure(
        source="predictive.accepted",
        zone_id="zone:living",
        module_id="light",
        metadata={"pattern_id": "pattern_positive"},
        outcome="executed",
    )
    _seed_closure(
        source="predictive.accepted",
        zone_id="zone:living",
        module_id="light",
        metadata={"pattern_id": "pattern_negative"},
        outcome="failed",
    )

    proposals = engine.generate_predictions({})

    assert len(proposals) >= 2
    assert proposals[0].pattern_id == "pattern_positive"
    assert proposals[0].confidence_score > proposals[1].confidence_score
    assert proposals[0].evidence["learning_signals"]["executed"] == 1
    assert proposals[1].evidence["learning_signals"]["problematic"] == 1
    assert "execution_outcomes" in proposals[0].source_signals


def test_habitus_zone_proposals_are_reprioritized_by_closure_history() -> None:
    miner = ZoneBasedMiner(_StubTagZoneIntegration(), MiningConfig())
    result = ZoneMiningResult("zone:living")
    result.filtered_rules = [
        Rule(
            A="binary_sensor.arrival:on",
            B="light.corner:on",
            dt_sec=90,
            nA=10,
            nB=10,
            nAB=8,
            confidence=0.8,
            confidence_lb=0.6,
            lift=1.8,
            leverage=0.2,
            observation_period_days=7,
            baseline_p_b=0.3,
        ),
        Rule(
            A="binary_sensor.couch_presence:on",
            B="light.sofa:on",
            dt_sec=90,
            nA=10,
            nB=10,
            nAB=8,
            confidence=0.8,
            confidence_lb=0.6,
            lift=1.8,
            leverage=0.2,
            observation_period_days=7,
            baseline_p_b=0.3,
        ),
    ]

    _seed_closure(
        source="proposal.accepted",
        zone_id="zone:living",
        module_id="light",
        metadata={
            "rule_a": "binary_sensor.arrival:on",
            "rule_b": "light.corner:on",
        },
        outcome="failed",
    )
    _seed_closure(
        source="proposal.accepted",
        zone_id="zone:living",
        module_id="light",
        metadata={
            "rule_a": "binary_sensor.couch_presence:on",
            "rule_b": "light.sofa:on",
        },
        outcome="executed",
    )

    proposals = miner.build_zone_proposals({"zone:living": result}, limit=10, min_confidence=0.55)

    assert len(proposals) == 2
    assert proposals[0]["trigger"]["entity_id"] == "binary_sensor.couch_presence"
    assert proposals[0]["learning_signals"]["executed"] == 1
    assert proposals[0]["priority_bias"] > proposals[1]["priority_bias"]
    assert proposals[1]["learning_signals"]["problematic"] == 1


def test_multizone_conflicts_prefer_actions_with_better_closure_history() -> None:
    _seed_closure(
        source="multizone.manual",
        zone_id="zone_living",
        module_id="light",
        subject_type="scene",
        service_call={
            "domain": "light",
            "service": "turn_on",
            "target": {
                "zone_id": "zone_living",
                "module_id": "light",
                "entity_id": "light.sofa",
            },
        },
        outcome="executed",
    )
    _seed_closure(
        source="multizone.manual",
        zone_id="zone_living",
        module_id="light",
        subject_type="scene",
        service_call={
            "domain": "light",
            "service": "turn_off",
            "target": {
                "zone_id": "zone_living",
                "module_id": "light",
                "entity_id": "light.sofa",
            },
        },
        outcome="failed",
    )

    engine = MultiZoneCoordinationEngine()
    scene_id = engine.create_scene(
        name="Arrival",
        description="Closure-guided ordering",
        zone_actions={
            "zone_living": [
                {
                    "module_id": "light",
                    "target": {"entity_id": "light.sofa"},
                    "action_type": "light.turn_on",
                    "priority": 5,
                },
                {
                    "module_id": "light",
                    "target": {"entity_id": "light.sofa"},
                    "action_type": "light.turn_off",
                    "priority": 5,
                },
            ]
        },
    )

    assert engine.activate_scene(scene_id, runtime_source="api.manual") is True

    pending = engine.get_pending_actions(entity_id="light.sofa")
    assert len(pending) == 1
    assert pending[0]["service"] == "turn_on"
    assert pending[0]["effective_priority"] > pending[0]["priority"]
    assert pending[0]["learning_signals"]["executed"] == 1
