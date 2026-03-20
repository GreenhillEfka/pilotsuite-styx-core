from copilot_core.habitat.homeassistant_adapter import normalize_outbound_payload
from copilot_core.ingest.event_store import EventStore


def test_normalize_outbound_payload_enriches_suggestion_with_contracts():
    payload = normalize_outbound_payload(
        "suggestion",
        {
            "title": "Wohnzimmer dimmen",
            "summary": "Abends das Hauptlicht dimmen.",
            "entity_id": "light.living_room_main",
            "service": "light.turn_on",
            "service_data": {"brightness_pct": 35},
            "zone_ids": ["zone:living"],
            "confidence": 0.84,
            "reason": "Sonnenuntergang und Anwesenheit erkannt.",
        },
    )

    assert payload["adapter"]["name"] == "homeassistant"
    assert payload["proposal_intent"]["module_id"] == "light"
    assert payload["proposal_intent"]["action_type"] == "light.turn_on"
    assert payload["proposal_intent"]["zone_id"] == "zone:living"
    assert payload["module_command"]["command_mode"] == "suggest"
    assert payload["module_command"]["target"]["entity_id"] == "light.living_room_main"
    assert payload["module_command"]["payload"]["brightness_pct"] == 35


def test_event_store_preserves_habitat_boundary_metadata(tmp_path):
    store = EventStore(store_path=str(tmp_path / "events.jsonl"))
    result = store.ingest_batch(
        [
            {
                "id": "evt-1",
                "ts": "2026-03-18T20:00:00+00:00",
                "type": "state_changed",
                "source": "home_assistant",
                "entity_id": "light.living_room_main",
                "attributes": {"domain": "light", "zone_ids": ["zone:living"]},
                "adapter": {"name": "homeassistant", "contract_version": "ha.input.v1"},
                "habitat_event": {"event_id": "hme:1", "module_id": "light", "event_type": "state_changed"},
                "neuron_input": {"input_id": "nin:1", "module_id": "light", "signal": "state_changed", "value": "on"},
            }
        ]
    )

    assert result["accepted"] == 1
    events = store.query(limit=1)
    assert events[0]["adapter"]["contract_version"] == "ha.input.v1"
    assert events[0]["habitat_event"]["event_id"] == "hme:1"
    assert events[0]["neuron_input"]["input_id"] == "nin:1"
