"""Hardening coverage for multizone handoff + scheduler runtime contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from copilot_core.multizone.coordination_engine import create_multi_zone_coordination_engine
from copilot_core.scheduler.engine import SchedulerEngine


def test_scheduler_bound_routine_executes_due_job_with_runtime_metadata() -> None:
    scheduler = SchedulerEngine()
    engine = create_multi_zone_coordination_engine(scheduler_engine=scheduler)

    past_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    routine_id = engine.create_routine(
        name="Scheduled Welcome",
        description="Scheduler should enqueue welcome action",
        trigger_type="time",
        trigger_config={"schedule_type": "once", "schedule_expression": past_time},
        zone_actions={
            "zone_entrance": [
                {
                    "module_id": "light",
                    "target": {"entity_id": "light.entrance"},
                    "action_type": "light.turn_on",
                    "data": {"brightness": 160},
                    "action_intent": {
                        "contract": "ActionIntentV1",
                        "action_id": "action:scheduler-welcome",
                        "zone_id": "zone_entrance",
                        "module_id": "light",
                        "action_type": "light.turn_on",
                        "target": {"entity_id": "light.entrance"},
                        "payload": {"brightness": 160},
                        "source": "proposal.accepted",
                    },
                }
            ]
        },
    )

    routine = engine._routines[routine_id]
    assert routine.scheduler_job_id is not None
    assert scheduler._jobs[routine.scheduler_job_id].action_name == "multizone.trigger_routine"

    processed = scheduler.process_due_jobs()
    assert processed == 1
    assert routine.trigger_count == 1
    assert routine.last_execution_source == "scheduler"

    pending = engine.get_pending_actions(zone_id="zone_entrance")
    assert len(pending) == 1
    action = pending[0]
    assert action["queue_source"] == "scheduler"
    assert action["subject_type"] == "routine"
    assert action["subject_id"] == routine_id
    assert action["scheduled_job_id"] == routine.scheduler_job_id
    assert action["targets"]["module"]["module_id"] == "light"
    assert action["targets"]["service"]["target"]["entity_id"] == "light.entrance"


def test_scene_activation_preserves_handoffs_and_real_targets() -> None:
    engine = create_multi_zone_coordination_engine()

    scene_id = engine.create_scene(
        name="Arrival Scene",
        description="Preserve proposal/action handoffs",
        proposal_handoff={"contract": "ProposalIntentV1", "proposal_id": "proposal:scene-arrival"},
        action_handoff={"contract": "ActionIntentV1", "action_id": "action:scene-arrival"},
        zone_actions={
            "zone_living": [
                {
                    "module_id": "light",
                    "target": {
                        "entity_id": "light.living_room",
                        "device_id": "device-living-light",
                    },
                    "action_type": "light.turn_on",
                    "payload": {"brightness": 200},
                    "proposal_intent": {
                        "contract": "ProposalIntentV1",
                        "proposal_id": "proposal:scene-arrival",
                        "zone_id": "zone_living",
                        "module_id": "light",
                        "action_type": "light.turn_on",
                        "target": {"entity_id": "light.living_room"},
                        "payload": {"brightness": 200},
                        "source": "proposal.accepted",
                    },
                    "action_intent": {
                        "contract": "ActionIntentV1",
                        "action_id": "action:scene-arrival",
                        "zone_id": "zone_living",
                        "module_id": "light",
                        "action_type": "light.turn_on",
                        "target": {"entity_id": "light.living_room"},
                        "payload": {"brightness": 200},
                        "source": "proposal.accepted",
                    },
                }
            ]
        },
    )

    activated = engine.activate_scene(scene_id, activated_by="api-test", runtime_source="api.manual")
    assert activated is True

    scene = next(item for item in engine.get_scenes() if item["scene_id"] == scene_id)
    assert scene["proposal_handoff"]["proposal_id"] == "proposal:scene-arrival"
    assert scene["action_handoff"]["action_id"] == "action:scene-arrival"
    assert scene["execution_contract"] == "MultiZoneSceneRuntimeV1"

    pending = engine.get_pending_actions(module_id="light")
    assert len(pending) == 1
    action = pending[0]
    assert action["proposal_intent"]["contract"] == "ProposalIntentV1"
    assert action["action_intent"]["contract"] == "ActionIntentV1"
    assert action["action_type"] == "light.turn_on"
    assert action["target"]["zone_id"] == "zone_living"
    assert action["targets"]["zone"]["zone_id"] == "zone_living"
    assert action["targets"]["module"]["device_id"] == "device-living-light"
    assert action["targets"]["service"]["payload"]["brightness"] == 200
