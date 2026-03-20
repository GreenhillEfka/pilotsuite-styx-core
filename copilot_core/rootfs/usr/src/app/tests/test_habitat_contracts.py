"""Tests for habitat-module contract dataclasses."""

from copilot_core.habitat import (
    DEFAULT_INPUT_MODEL,
    ActionIntent,
    HabitatModuleCommand,
    HabitatModuleEvent,
    NeuronInput,
    ProposalIntent,
)


class TestHabitatModuleEvent:
    def test_event_round_trip_and_neuron_input_conversion(self):
        event = HabitatModuleEvent.from_dict(
            {
                "event_id": "hme:test-1",
                "module_id": "light",
                "event_type": "state_changed",
                "entity_id": "light.living_room_main",
                "zone_id": "zone:living",
                "state": "on",
                "attributes": {"brightness_pct": 65},
                "context": {"source": "homeassistant"},
                "tags": ["ambient", "presence"],
                "occurred_at_ms": 1710000000000,
            }
        )

        assert event.domain == "light"
        assert event.to_dict()["input_model"] == DEFAULT_INPUT_MODEL

        neuron_input = event.to_neuron_input(
            signal="ambient_need",
            confidence=0.82,
            neuron_targets=["ambient_need", "presence_intent"],
        )

        assert isinstance(neuron_input, NeuronInput)
        assert neuron_input.source_event_id == "hme:test-1"
        assert neuron_input.module_id == "light"
        assert neuron_input.zone_id == "zone:living"
        assert neuron_input.entity_id == "light.living_room_main"
        assert neuron_input.domain == "light"
        assert neuron_input.signal == "ambient_need"
        assert neuron_input.value == "on"
        assert neuron_input.confidence == 0.82
        assert neuron_input.context["event_type"] == "state_changed"
        assert neuron_input.metadata["brightness_pct"] == 65


class TestProposalIntent:
    def test_defaults_stay_suggestion_first(self):
        proposal = ProposalIntent(
            module_id="light",
            action_type="light.turn_on",
            title="Wohnzimmerlicht einschalten",
            summary="Wenn Präsenz erkannt wird, soll das Hauptlicht angehen.",
            zone_id="zone:living",
            target={"entity_id": "light.living_room_main"},
            payload={"brightness_pct": 55},
            confidence=0.91,
        )

        assert proposal.can_auto_execute() is False

        action = proposal.to_action_intent()
        assert action.can_execute() is False

        command = HabitatModuleCommand.from_proposal_intent(proposal)
        assert command.command_mode == "suggest"
        assert command.metadata["approval_required"] is True
        assert command.metadata["requires_confirmation"] is True

    def test_explicit_autonomous_policy_can_auto_execute(self):
        proposal = ProposalIntent(
            module_id="climate",
            action_type="climate.set_temperature",
            title="Bad leicht vorwärmen",
            summary="Vor dem Duschen wird die Zieltemperatur angehoben.",
            zone_id="zone:bath",
            target={"entity_id": "climate.bath"},
            payload={"temperature": 22},
            confidence=0.88,
            autonomy_mode="autonomous",
            direct_execution_enabled=True,
            approval_required=False,
            requires_confirmation=False,
        )

        assert proposal.can_auto_execute() is True

        action = proposal.to_action_intent()
        assert action.can_execute() is True

        command = action.to_module_command()
        assert command.command_mode == "execute"


class TestActionIntent:
    def test_manual_approval_overrides_learning_mode(self):
        action = ActionIntent(
            module_id="music",
            action_type="media_player.volume_set",
            zone_id="zone:living",
            target={"entity_id": "media_player.living_room"},
            payload={"volume_level": 0.22},
            autonomy_mode="learning",
            direct_execution_enabled=False,
            approval_required=True,
            requires_confirmation=True,
            approved=True,
        )

        assert action.can_execute() is True
        command = HabitatModuleCommand.from_action_intent(action)
        assert command.command_mode == "execute"
        assert command.approved is True

    def test_off_mode_blocks_execution_even_if_approved(self):
        action = ActionIntent(
            module_id="camera",
            action_type="camera.record",
            zone_id="zone:outside",
            target={"entity_id": "camera.garden"},
            autonomy_mode="off",
            approved=True,
        )

        assert action.can_execute() is False
        command = HabitatModuleCommand.from_action_intent(action)
        assert command.command_mode == "suggest"
