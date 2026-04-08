"""Tests for Voice Integration Module.

Tests voice intent handling, context building, and proactive hints.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from copilot_core.voice.voice_handler import (
    VoiceIntentHandler,
    VoiceIntent,
    IntentType,
    VoiceResponse,
)
from copilot_core.voice.context_builder import (
    VoiceContextBuilder,
    VoiceContext,
    TimeContext,
    ZoneContext,
    TimeOfDay,
    DayType,
)
from copilot_core.voice.proactive import (
    ProactiveVoiceHints,
    ProactiveHint,
    HintConfig,
    HintPriority,
    HintType,
)


class TestVoiceIntentHandler:
    """Tests for VoiceIntentHandler."""
    
    def test_parse_intent_light_on_de(self):
        """Test German light on intent parsing."""
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Mach das Licht an")
        
        assert intent.intent_type == IntentType.LIGHT_ON
        assert intent.confidence > 0.5
        assert intent.language == "de"
    
    def test_parse_intent_light_off_de(self):
        """Test German light off intent parsing."""
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Licht aus")
        
        assert intent.intent_type == IntentType.LIGHT_OFF
        assert intent.confidence > 0.5
    
    def test_parse_intent_light_on_en(self):
        """Test English light on intent parsing."""
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Turn on the light")
        
        assert intent.intent_type == IntentType.LIGHT_ON
        assert intent.language == "en"
    
    def test_parse_intent_climate_set(self):
        """Test climate set intent with temperature slot."""
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Stell die Temperatur auf 21 Grad")
        
        assert intent.intent_type == IntentType.CLIMATE_SET
        assert intent.slots.get("temperature") == 21
        assert intent.route == "tier1_regex"
        assert intent.clarification_needed is False

    def test_parse_intent_climate_missing_slot_requests_clarification(self):
        """Recognised but incomplete commands should ask for missing slots."""
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Stell die Temperatur")

        assert intent.intent_type == IntentType.CLIMATE_SET
        assert "target_temp" in intent.missing_slots
        assert intent.clarification_needed is True
        assert intent.route == "tier2_ml"
        assert intent.clarification_prompt is not None
    
    def test_parse_intent_media_play(self):
        """Test media play intent parsing."""
        handler = VoiceIntentHandler()
        # Test both German and English
        intent_de = handler.parse_intent("Spiel Musik")
        intent_en = handler.parse_intent("Play music")
        
        # At least one should match MEDIA_PLAY
        assert intent_de.intent_type == IntentType.MEDIA_PLAY or intent_en.intent_type == IntentType.MEDIA_PLAY
    
    def test_parse_intent_unknown(self):
        """Test unknown intent handling."""
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Random gibberish xyz123")
        
        assert intent.intent_type == IntentType.UNKNOWN
        assert intent.confidence == 0.0
    
    def test_handle_intent_unknown(self):
        """Test handling unknown intent."""
        handler = VoiceIntentHandler()
        intent = VoiceIntent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            language="de",
            raw_text="Unknown text",
            route="tier3_llm",
            route_reason="unknown_intent",
        )
        
        response = handler.handle_intent(intent)
        
        assert response.tts_text != ""
        assert response.language == "de"
        assert response.actions == []
        assert response.route == "tier3_llm"

    def test_handle_intent_returns_clarification_response(self):
        """Test clarification responses do not execute actions."""
        handler = VoiceIntentHandler()
        intent = handler.parse_intent("Stell die Temperatur")

        response = handler.handle_intent(intent, VoiceContext(language_preference="de"))

        assert response.clarification_needed is True
        assert response.actions == []
        assert "grad" in response.tts_text.lower()
    
    def test_handle_intent_light_on(self):
        """Test handling light on intent."""
        handler = VoiceIntentHandler()
        intent = VoiceIntent(
            intent_type=IntentType.LIGHT_ON,
            confidence=0.9,
            language="de",
            raw_text="Licht an",
        )
        
        context = VoiceContext(
            zone_name="wohnzimmer",
            language_preference="de",
        )
        
        response = handler.handle_intent(intent, context)
        
        assert response.intent_type == IntentType.LIGHT_ON
        assert len(response.actions) > 0
        assert response.actions[0]["service"] == "turn_on"
        assert "licht" in response.tts_text.lower() or "an" in response.tts_text.lower()
    
    def test_handle_intent_time_query(self):
        """Test handling time query intent."""
        handler = VoiceIntentHandler()
        intent = VoiceIntent(
            intent_type=IntentType.TIME_QUERY,
            confidence=0.95,
            language="de",
        )
        
        response = handler.handle_intent(intent)
        
        assert "uhr" in response.tts_text.lower() or ":" in response.tts_text
    
    def test_language_detection_german(self):
        """Test German language detection."""
        handler = VoiceIntentHandler()
        language = handler._detect_language("Mach das Licht an")
        
        assert language == "de"
    
    def test_language_detection_english(self):
        """Test English language detection."""
        handler = VoiceIntentHandler()
        language = handler._detect_language("Turn on the light")
        
        assert language == "en"


class TestVoiceContextBuilder:
    """Tests for VoiceContextBuilder."""
    
    def test_build_time_context_morning(self):
        """Test time context for morning hours."""
        builder = VoiceContextBuilder()
        now = datetime(2026, 3, 2, 9, 30, tzinfo=timezone.utc)  # Monday morning (March 2, 2026 is Monday)
        
        time_context = builder._build_time_context(now)
        
        assert time_context.time_of_day == TimeOfDay.MORNING
        assert time_context.day_type == DayType.WEEKDAY
        assert time_context.hour == 9
        assert "morgen" in time_context.description_de.lower()
    
    def test_build_time_context_evening(self):
        """Test time context for evening hours."""
        builder = VoiceContextBuilder()
        now = datetime(2026, 3, 1, 20, 0, tzinfo=timezone.utc)  # Sunday evening
        
        time_context = builder._build_time_context(now)
        
        assert time_context.time_of_day == TimeOfDay.EVENING
        assert time_context.day_type == DayType.WEEKEND
        assert "abend" in time_context.description_de.lower()
    
    def test_build_time_context_night(self):
        """Test time context for night hours."""
        builder = VoiceContextBuilder()
        now = datetime(2026, 3, 1, 2, 0, tzinfo=timezone.utc)  # 2 AM
        
        time_context = builder._build_time_context(now)
        
        assert time_context.time_of_day == TimeOfDay.NIGHT
        assert time_context.is_quiet_hours is True
    
    def test_build_zone_context_living_room(self):
        """Test zone context for living room."""
        builder = VoiceContextBuilder()
        
        zone_context = builder._build_zone_context("wohnzimmer", None)
        
        assert zone_context.zone_name == "wohnzimmer"
        assert zone_context.zone_type == "living_room"
        assert "relaxen" in zone_context.typical_activities
    
    def test_build_zone_context_bedroom(self):
        """Test zone context for bedroom."""
        builder = VoiceContextBuilder()
        
        zone_context = builder._build_zone_context("schlafzimmer", None)
        
        assert zone_context.zone_type == "bedroom"
        assert "schlafen" in zone_context.typical_activities
    
    def test_build_context_basic(self):
        """Test basic context building."""
        builder = VoiceContextBuilder()
        
        context = builder.build_context(
            mood_engine=None,
            habitus_service=None,
            zone_name="wohnzimmer",
        )
        
        assert context.zone_name == "wohnzimmer"
        assert context.time_context is not None
        assert context.timestamp is not None
    
    def test_build_context_with_sensor_data(self):
        """Test context building with sensor data."""
        builder = VoiceContextBuilder()
        
        sensor_data = {
            "binary_sensor.wohnzimmer_motion": {"state": "on"},
            "sensor.wohnzimmer_illuminance": {"state": "150"},
            "light.wohnzimmer": {"state": "on"},
        }
        
        context = builder.build_context(
            mood_engine=None,
            habitus_service=None,
            zone_name="wohnzimmer",
            sensor_data=sensor_data,
        )
        
        assert context.current_zone is not None
        assert context.current_zone.is_occupied is True
        assert len(context.active_devices) > 0
    
    def test_cache_context(self):
        """Test context caching."""
        builder = VoiceContextBuilder()
        
        # Build context
        context1 = builder.build_context(zone_name="test_zone")
        
        # Get cached context
        cached = builder.get_cached_context("test_zone")
        
        assert cached is not None
        assert cached.zone_name == "test_zone"
    
    def test_clear_cache(self):
        """Test cache clearing."""
        builder = VoiceContextBuilder()
        
        builder.build_context(zone_name="test_zone")
        builder.clear_cache()
        
        cached = builder.get_cached_context("test_zone")
        assert cached is None


class TestProactiveVoiceHints:
    """Tests for ProactiveVoiceHints."""
    
    def test_generate_hints_empty(self):
        """Test hint generation with no triggers."""
        hints_service = ProactiveVoiceHints()
        
        context = VoiceContext(
            zone_name="wohnzimmer",
            language_preference="de",
        )
        
        hints = hints_service.generate_hints(context, force=True)
        
        # Should have some hints due to force=True
        assert isinstance(hints, list)
    
    def test_hint_priority_ordering(self):
        """Test that hints are sorted by priority."""
        hints_service = ProactiveVoiceHints()
        
        context = VoiceContext(
            zone_name="wohnzimmer",
            language_preference="de",
        )
        
        hints = hints_service.generate_hints(context, force=True)
        
        if len(hints) > 1:
            priority_order = {
                HintPriority.CRITICAL: 0,
                HintPriority.HIGH: 1,
                HintPriority.MEDIUM: 2,
                HintPriority.LOW: 3,
            }
            
            for i in range(len(hints) - 1):
                assert priority_order[hints[i].priority] <= priority_order[hints[i + 1].priority]
    
    def test_hint_message_language(self):
        """Test hint message language selection."""
        hint = ProactiveHint(
            hint_type=HintType.MOOD_SUGGESTION,
            priority=HintPriority.LOW,
            title_de="Test DE",
            title_en="Test EN",
            message_de="Nachricht auf Deutsch",
            message_en="Message in English",
        )
        
        assert hint.get_message("de") == "Nachricht auf Deutsch"
        assert hint.get_message("en") == "Message in English"
        assert hint.get_title("de") == "Test DE"
        assert hint.get_title("en") == "Test EN"
    
    def test_hint_to_dict(self):
        """Test hint serialization to dict."""
        hint = ProactiveHint(
            hint_type=HintType.TIME_ROUTINE,
            priority=HintPriority.MEDIUM,
            title_de="Test",
            title_en="Test",
            message_de="Test",
            message_en="Test",
            suggested_action={"domain": "light", "service": "turn_on"},
        )
        
        hint_dict = hint.to_dict()
        
        assert hint_dict["hint_type"] == "time_routine"
        assert hint_dict["priority"] == "medium"
        assert hint_dict["suggested_action"] is not None
        assert "created_at" in hint_dict
    
    def test_config_priority_filter(self):
        """Test hint filtering by priority."""
        config = HintConfig(
            min_priority=HintPriority.HIGH,
        )
        hints_service = ProactiveVoiceHints(config=config)
        
        # Create low priority hint (should be filtered)
        low_hint = ProactiveHint(
            hint_type=HintType.MOOD_SUGGESTION,
            priority=HintPriority.LOW,
            title_de="Test",
            title_en="Test",
            message_de="Test",
            message_en="Test",
        )
        
        # Create high priority hint (should pass)
        high_hint = ProactiveHint(
            hint_type=HintType.MOOD_CHANGE,
            priority=HintPriority.HIGH,
            title_de="Test",
            title_en="Test",
            message_de="Test",
            message_en="Test",
        )
        
        filtered = hints_service._filter_hints([low_hint, high_hint], force=True)
        
        assert len(filtered) == 1
        assert filtered[0].priority == HintPriority.HIGH
    
    def test_get_critical_hints(self):
        """Test getting only critical hints."""
        hints_service = ProactiveVoiceHints()
        
        context = VoiceContext()
        
        # Get critical hints
        critical = hints_service.get_critical_hints(context)
        
        for hint in critical:
            assert hint.priority == HintPriority.CRITICAL
    
    def test_clear_tracking(self):
        """Test clearing hint tracking."""
        hints_service = ProactiveVoiceHints()
        
        # Generate some hints to populate tracking
        hints_service.generate_hints(VoiceContext(), force=True)
        
        # Clear tracking
        hints_service.clear_tracking()
        
        assert len(hints_service._last_hints) == 0
        assert hints_service._hints_this_hour == 0


class TestVoiceAPIEndpoints:
    """Tests for Voice API endpoints (integration tests)."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from flask import Flask
        from copilot_core.api.v1.voice import bp as voice_bp
        
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["COPILOT_CFG"] = type('Config', (), {
            "version": "test",
            "log_level": "info",
            "auth_token": "test",
            "data_dir": "/tmp",
            "events_persist": False,
            "events_jsonl_path": "/tmp/events.jsonl",
            "events_cache_max": 500,
            "events_idempotency_ttl_seconds": 1200,
            "events_idempotency_lru_max": 10000,
            "candidates_persist": False,
            "candidates_json_path": "/tmp/candidates.json",
            "candidates_max": 500,
            "mood_window_seconds": 3600,
            "brain_graph_persist": True,
            "brain_graph_json_path": "/tmp/brain_graph.json",
            "brain_graph_nodes_max": 500,
            "brain_graph_edges_max": 1500,
        })()
        
        # Mock the auth validation
        def mock_validate_token(request):
            return True
        
        # The blueprint has url_prefix="/api/v1/voice"
        with patch('copilot_core.api.v1.voice._validate_token', mock_validate_token):
            app.register_blueprint(voice_bp)

            with app.test_client() as client:
                yield client

    def test_voice_status_endpoint(self, client):
        """Test voice status endpoint."""
        response = client.get(
            "/api/v1/voice/status",
        )

        # Should return 200 (success)
        assert response.status_code == 200

    def test_voice_context_endpoint(self, client):
        """Test voice context endpoint."""
        response = client.get(
            "/api/v1/voice/context",
        )

        assert response.status_code == 200

    def test_voice_intents_endpoint(self, client):
        """Test voice intents endpoint."""
        response = client.get(
            "/api/v1/voice/intents",
        )

        assert response.status_code == 200

        if response.status_code == 200:
            data = response.get_json()
            assert "intents" in data
            assert len(data["intents"]) > 0

    def test_voice_zones_endpoint(self, client):
        """Test voice zones endpoint."""
        response = client.get(
            "/api/v1/voice/zones",
        )

        assert response.status_code == 200

        if response.status_code == 200:
            data = response.get_json()
            assert "zones" in data

    def test_voice_intent_endpoint_post(self, client):
        """Test voice intent processing endpoint."""
        response = client.post(
            "/api/v1/voice/intent",
            json={"text": "Licht an", "language": "de"},
        )
        
        assert response.status_code == 200
        
        if response.status_code == 200:
            data = response.get_json()
            assert "status" in data
            assert "intent" in data
            assert "response" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
