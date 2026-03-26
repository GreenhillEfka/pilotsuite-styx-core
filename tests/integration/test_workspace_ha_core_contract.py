"""Workspace contract tests for HA↔Core interplay.

These tests deliberately span both repos inside the shared workspace:
- HA repo provides the adapter boundary payload builders
- Core repo provides canonical entity classification

This gives PilotSuite a non-live integration lane that can run entirely in the
workspace without depending on Home Assistant installation state.
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
HA_REPO_ROOT = REPO_ROOT.parent / "pilotsuite-styx-ha"

for path in (CORE_APP_ROOT, HA_REPO_ROOT):
    path_str = str(path)
    if path.exists() and path_str not in sys.path:
        sys.path.insert(0, path_str)


from copilot_core.core.taxonomy import classify_entity  # noqa: E402
from custom_components.copilot_ha.habitat_adapter import (  # noqa: E402
    build_call_service_forward_item,
    build_state_changed_forward_item,
    normalize_received_webhook_payload,
)


def test_workspace_state_changed_payload_is_core_classifiable() -> None:
    item = build_state_changed_forward_item(
        item_id="evt-workspace-1",
        ts="2026-03-26T17:00:00+00:00",
        entity_id="light.living_room_main",
        old_state="off",
        new_state="on",
        zone_ids=["zone:living"],
        state_attributes={"brightness_pct": 55},
        neuron_tags=["ambient_need"],
        occurred_at_ms=1774544400000,
    )

    classification = classify_entity(item["entity_id"], item["habitat_event"]["state"])

    assert item["adapter"]["contract_version"] == "ha.input.v1"
    assert item["habitat_event"]["zone_id"] == "zone:living"
    assert item["neuron_input"]["zone_id"] == "zone:living"
    assert item["neuron_input"]["signal"] == "state_changed"
    assert classification.role.value == "lights"
    assert classification.module_bucket == "licht"
    assert "ambient" in classification.tags
    assert "indoor" in classification.tags


def test_workspace_call_service_payload_maps_to_motion_lane() -> None:
    item = build_call_service_forward_item(
        item_id="evt-workspace-2",
        ts="2026-03-26T17:01:00+00:00",
        domain="binary_sensor",
        service="turn_on",
        entity_ids=["binary_sensor.bad_motion"],
        zone_ids=["zone:bath"],
        occurred_at_ms=1774544460000,
    )

    classification = classify_entity(item["entity_id"], "on")

    assert item["adapter"]["contract_version"] == "ha.input.v1"
    assert item["habitat_event"]["event_type"] == "call_service"
    assert item["neuron_input"]["signal"] == "binary_sensor.turn_on"
    assert classification.role.value == "motion"
    assert classification.module_bucket == "bewegung"
    assert "critical" in classification.tags


def test_workspace_core_suggestion_normalizes_back_to_ha_command() -> None:
    classification = classify_entity("light.living_room_main", "on")

    payload = normalize_received_webhook_payload(
        "suggestion",
        {
            "title": "Wohnzimmer dimmen",
            "summary": "Abends das Hauptlicht dimmen.",
            "entity_id": classification.entity_id,
            "service": "light.turn_on",
            "service_data": {"brightness_pct": 35},
            "zone_ids": ["zone:living"],
            "confidence": 0.91,
        },
    )

    assert payload["adapter"]["direction"] == "core_to_homeassistant"
    assert payload["adapter"]["contract_version"] == "ha.output.v1"
    assert payload["proposal_intent"]["module_id"] == classification.domain
    assert payload["proposal_intent"]["action_type"] == "light.turn_on"
    assert payload["module_command"]["target"]["entity_id"] == classification.entity_id
    assert payload["module_command"]["payload"]["brightness_pct"] == 35
