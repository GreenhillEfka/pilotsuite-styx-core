"""Workspace contract tests for HA↔Core interplay.

These tests deliberately span both repos inside the shared workspace:
- HA repo provides the adapter boundary payload builders
- Core repo provides canonical entity classification

This gives PilotSuite a non-live integration lane that can run entirely in the
workspace without depending on Home Assistant installation state.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"
HA_REPO_ROOT = REPO_ROOT.parent / "pilotsuite-styx-ha"
SANDBOX_ROOT = REPO_ROOT.parent.parent / "workspaces" / "pilotsuite-stxy-sandbox"
HABITAT_ADAPTER_PATH = HA_REPO_ROOT / "custom_components" / "copilot_ha" / "habitat_adapter.py"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.core.taxonomy import classify_entity  # noqa: E402
from copilot_core.api.v1.zone_automation import (  # noqa: E402
    init_zone_automation_api,
    sync_zone_definitions,
)
from copilot_core.hub.zone_automation import ZoneAutomationController  # noqa: E402
from copilot_core.ingest.event_store import EventStore  # noqa: E402


_adapter_spec = spec_from_file_location("workspace_habitat_adapter", HABITAT_ADAPTER_PATH)
assert _adapter_spec and _adapter_spec.loader, f"missing habitat adapter at {HABITAT_ADAPTER_PATH}"
_habitat_adapter = module_from_spec(_adapter_spec)
_adapter_spec.loader.exec_module(_habitat_adapter)

build_call_service_forward_item = _habitat_adapter.build_call_service_forward_item
build_state_changed_forward_item = _habitat_adapter.build_state_changed_forward_item
normalize_received_webhook_payload = _habitat_adapter.normalize_received_webhook_payload


def _load_sandbox_fixture(relative_path: str) -> dict:
    with (SANDBOX_ROOT / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


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



def test_workspace_zone_sync_fixture_binds_to_core_api_contract() -> None:
    fixture = _load_sandbox_fixture("fixtures/ha_events/zone_definitions.json")

    controller = ZoneAutomationController()
    init_zone_automation_api(controller)

    app = Flask(__name__)
    app.config["TESTING"] = True

    with app.test_request_context(
        "/api/v1/zone-automation/sync-definitions",
        method="POST",
        json=fixture,
    ):
        response = sync_zone_definitions.__wrapped__()

    body = response.get_json()
    assert body["ok"] is True
    assert body["count"] == 2
    assert sorted(body["synced"]) == ["badbereich", "wohnbereich"]

    wohn = controller.get_zone_config("wohnbereich")
    bad = controller.get_zone_config("badbereich")
    assert wohn.zone_name == "Wohnbereich"
    assert wohn.zone_type == "living"
    assert len(getattr(wohn, "_ha_entities", [])) == 2
    assert bad.zone_name == "Badbereich"
    assert bad.zone_type == "bath"



def test_workspace_fallback_lane_accepts_canonical_and_legacy_state_changed() -> None:
    store = EventStore(store_path=str(REPO_ROOT / "tmp" / "workspace-contract-events.jsonl"))

    canonical = _load_sandbox_fixture("fixtures/ha_events/canonical_state_changed.json")
    legacy = _load_sandbox_fixture("fixtures/ha_events/legacy_state_changed.json")

    result = store.ingest_batch([canonical, legacy])
    assert result["accepted"] == 2
    assert result["rejected"] == 0

    events = store.query(limit=10)
    assert len(events) == 2

    canonical_event = events[0]
    legacy_event = events[1]

    assert canonical_event["kind"] == "state_changed"
    assert canonical_event["src"] == "ha"
    assert canonical_event["zone_id"] == "wohnbereich"
    assert canonical_event["new"]["attrs"]["brightness"] == 180
    assert canonical_event["context_id"] == "ctxcanonical"

    assert legacy_event["kind"] == "state_changed"
    assert legacy_event["src"] == "ha"
    assert legacy_event["zone_id"] == "wohnbereich"
    assert legacy_event["new"]["state"] == "on"
    assert legacy_event["new"]["attrs"]["brightness"] == 140
    assert legacy_event["trigger"] == "automation"
    assert legacy_event["context_id"] == "ctxlegacy123"



def test_workspace_call_service_fixture_normalizes_to_core_contract() -> None:
    store = EventStore(store_path=str(REPO_ROOT / "tmp" / "workspace-contract-events-call.jsonl"))
    call_service = _load_sandbox_fixture("fixtures/ha_events/call_service.json")

    result = store.ingest_batch([call_service])
    assert result["accepted"] == 1
    assert result["rejected"] == 0

    stored = store.query(limit=10)[0]
    assert stored["kind"] == "call_service"
    assert stored["src"] == "ha"
    assert stored["service"]["domain"] == "light"
    assert stored["service"]["service"] == "turn_on"
    assert stored["service"]["entity_ids"] == ["light.living_room_main"]
    assert stored["zone_id"] == "wohnbereich"
