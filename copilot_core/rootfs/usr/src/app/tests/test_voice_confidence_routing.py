"""Tests for Task 2 voice confidence scoring and routing."""

from copilot_core.voice.confidence_router import (
    ConfidenceRouter,
    ProcessingTier,
    RoutingDecision,
)
from copilot_core.voice.context_builder import VoiceContext
from copilot_core.voice.intent_parser import IntentParser
from copilot_core.voice.voice_handler import IntentType, VoiceIntentHandler


class TestIntentParser:
    def test_parse_full_light_command_high_confidence(self):
        parser = IntentParser()

        result = parser.parse("Schalte das Licht im Wohnzimmer an")

        assert result.intent == "light.turn_on"
        assert result.slots["room"] == "wohnzimmer"
        assert result.missing_slots == []
        assert result.confidence >= 0.85
        assert result.clarification_needed is False

    def test_parse_partial_light_command_executes_without_room_slot(self):
        parser = IntentParser()

        result = parser.parse("Mach das Licht an")

        assert result.intent == "light.turn_on"
        assert result.missing_slots == []
        assert result.clarification_needed is False
        assert result.confidence >= 0.85

    def test_parse_temperature_with_float_slot(self):
        parser = IntentParser()

        result = parser.parse("Stelle die Temperatur im Bad auf 21,5 Grad")

        assert result.intent == "climate.set_temperature"
        assert result.slots["room"] == "bad"
        assert result.slots["target_temp"] == 21.5
        assert result.confidence >= 0.85

    def test_unknown_command_returns_suggestions(self):
        parser = IntentParser()

        result = parser.parse("Bitte mach irgendwas Nettes mit dem Licht")

        assert result.intent == "unknown"
        assert result.confidence < 0.60
        assert "light.turn_on" in result.suggested_intents


class TestConfidenceRouter:
    def test_router_executes_high_confidence_match(self):
        parser = IntentParser()
        router = ConfidenceRouter()

        result = parser.parse("Schalte das Licht im Wohnzimmer aus")
        route = router.route(result)

        assert route.decision == RoutingDecision.EXECUTE
        assert route.processing_tier == ProcessingTier.REGEX
        assert route.reason == "high_confidence"

    def test_router_clarifies_missing_slots(self):
        parser = IntentParser()
        router = ConfidenceRouter()

        result = parser.parse("Stell die Temperatur")
        route = router.route(result)

        assert route.decision == RoutingDecision.CLARIFY
        assert route.processing_tier == ProcessingTier.ML
        assert route.reason == "missing_slots"
        assert "grad" in route.clarification_prompt.lower()

    def test_router_falls_back_for_unknown_intent(self):
        parser = IntentParser()
        router = ConfidenceRouter()

        result = parser.parse("Abrakadabra Simsalabim")
        route = router.route(result)

        assert route.decision == RoutingDecision.FALLBACK
        assert route.processing_tier == ProcessingTier.LLM
        assert route.reason == "unknown_intent"


class TestVoiceHandlerIntegration:
    def test_voice_handler_surfaces_clarification_prompt(self):
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Stell die Temperatur", language="de")

        response = handler.handle_intent(intent, VoiceContext(zone_name="unknown", language_preference="de"))

        assert intent.intent_type == IntentType.CLIMATE_SET
        assert intent.clarification_needed is True
        assert response.actions == []
        assert "grad" in response.tts_text.lower()

    def test_voice_handler_uses_explicit_room_slot(self):
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Mach das Licht im Wohnzimmer an", language="de")

        response = handler.handle_intent(intent, VoiceContext(zone_name="unknown", language_preference="de"))

        assert response.intent_type == IntentType.LIGHT_ON
        assert response.actions[0]["entity_id"] == "light.wohnzimmer"
        assert intent.clarification_needed is False
        assert intent.slots["room"] == "wohnzimmer"
