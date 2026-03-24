"""Tests for homeassistant/habitat_adapter.py"""
from __future__ import annotations

import pytest

from copilot_core.homeassistant.habitat_adapter import (
    ADAPTER_ID,
    INBOUND_CONTRACT_VERSION,
    OUTBOUND_CONTRACT_VERSION,
    build_state_changed_forward_item,
    build_call_service_forward_item,
    wrap_ha_state_changed,
    wrap_ha_service_call,
    normalize_received_webhook_payload,
    wrap_core_proposal,
    wrap_core_action,
)


class TestIdentity:
    def test_adapter_id(self):
        assert ADAPTER_ID == "homeassistant"

    def test_contract_versions(self):
        assert INBOUND_CONTRACT_VERSION == "ha.input.v1"
        assert OUTBOUND_CONTRACT_VERSION == "ha.output.v1"


class TestInboundStateChanged:
    def test_build_state_changed_basic(self):
        item = build_state_changed_forward_item(
            item_id="evt-123",
            ts="2026-03-24T10:00:00Z",
            entity_id="light.living_room",
            old_state="off",
            new_state="on",
        )

        assert item["id"] == "evt-123"
        assert item["type"] == "state_changed"
        assert item["source"] == "home_assistant"
        assert item["entity_id"] == "light.living_room"
        assert item["attributes"]["domain"] == "light"
        assert item["attributes"]["old_state"] == "off"
        assert item["attributes"]["new_state"] == "on"

        # Check adapter metadata
        assert item["adapter"]["name"] == "homeassistant"
        assert item["adapter"]["direction"] == "homeassistant_to_core"
        assert item["adapter"]["contract_version"] == INBOUND_CONTRACT_VERSION

        # Check neuron_input
        nin = item["neuron_input"]
        assert nin["input_id"] == "nin:evt-123"
        assert nin["module_id"] == "light"
        assert nin["signal"] == "state_changed"
        assert nin["value"] == "on"
        assert nin["zone_id"] is None

    def test_build_state_changed_with_zones(self):
        item = build_state_changed_forward_item(
            item_id="evt-456",
            ts="2026-03-24T10:00:00Z",
            entity_id="sensor.temperature_bedroom",
            old_state="21.0",
            new_state="22.5",
            zone_ids=["bedroom"],
            neuron_tags=["climate"],
        )

        assert item["neuron_input"]["zone_id"] == "bedroom"
        assert "climate" in item["neuron_input"]["tags"]
        assert item["neuron_input"]["neuron_targets"] == ["climate"]

    def test_wrap_ha_state_changed_convenience(self):
        item = wrap_ha_state_changed(
            item_id="evt-789",
            ts="2026-03-24T10:00:00Z",
            entity_id="climate.thermostat",
            old_state="heat",
            new_state="auto",
        )
        assert item["type"] == "state_changed"
        assert item["neuron_input"]["domain"] == "climate"


class TestInboundCallService:
    def test_build_call_service_basic(self):
        item = build_call_service_forward_item(
            item_id="svc-001",
            ts="2026-03-24T10:00:00Z",
            domain="light",
            service="turn_on",
            entity_ids=["light.kitchen", "light.dining"],
            zone_ids=["kitchen"],
        )

        assert item["id"] == "svc-001"
        assert item["type"] == "call_service"
        assert item["source"] == "home_assistant"
        assert item["attributes"]["domain"] == "light"
        assert item["attributes"]["service"] == "turn_on"
        assert item["attributes"]["entity_ids"] == ["light.kitchen", "light.dining"]

        # Check neuron_input
        nin = item["neuron_input"]
        assert nin["signal"] == "light.turn_on"
        assert nin["module_id"] == "light"
        assert nin["zone_id"] == "kitchen"


class TestOutboundProposal:
    def test_normalize_suggestion(self):
        data = {
            "proposal_id": "prop-001",
            "module_id": "light",
            "action_type": "light.turn_on",
            "target": {"entity_id": "light.living_room"},
            "payload": {"brightness": 80},
            "confidence": 0.85,
            "explanation": "Energy savings opportunity",
            "zone_id": "living",
        }
        result = normalize_received_webhook_payload("suggestion", data)

        assert "proposal_intent" in result
        assert result["proposal_intent"]["proposal_id"] == "prop-001"
        assert result["proposal_intent"]["module_id"] == "light"
        assert result["proposal_intent"]["zone_id"] == "living"
        assert result["proposal_intent"]["confidence"] == 0.85
        assert "module_command" in result
        assert result["module_command"]["command_mode"] == "suggest"

    def test_wrap_core_proposal_convenience(self):
        result = wrap_core_proposal(
            proposal_id="prop-002",
            module_id="climate",
            action_type="climate.set_temperature",
            target={"entity_id": "climate.thermostat"},
            payload={"temperature": 21.0},
            confidence=0.9,
            explanation="Comfort preference",
            zone_id="bedroom",
        )
        assert result["proposal_intent"]["proposal_id"] == "prop-002"
        assert result["proposal_intent"]["zone_id"] == "bedroom"


class TestOutboundAction:
    def test_normalize_autonomy_executed(self):
        data = {
            "action_id": "act-001",
            "proposal_id": "prop-001",
            "module_id": "light",
            "action_type": "light.turn_on",
            "target": {"entity_id": "light.living_room"},
            "payload": {"brightness": 100},
            "confidence": 1.0,
            "approved": True,
        }
        result = normalize_received_webhook_payload("autonomy_executed", data)

        assert "action_intent" in result
        assert result["action_intent"]["action_id"] == "act-001"
        assert result["action_intent"]["approved"] is True
        assert result["module_command"]["command_mode"] == "execute"

    def test_wrap_core_action_convenience(self):
        result = wrap_core_action(
            action_id="act-002",
            module_id="climate",
            action_type="climate.set_temperature",
            target={"entity_id": "climate.bedroom"},
            payload={"temperature": 19.0},
            approved=True,
            proposal_id="prop-002",
        )
        assert result["action_intent"]["action_id"] == "act-002"
        assert result["action_intent"]["approved"] is True
        assert result["module_command"]["command_mode"] == "execute"
