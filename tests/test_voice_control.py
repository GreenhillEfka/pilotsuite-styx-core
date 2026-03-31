"""Tests for Voice Control Engine — Slice 16."""
import pytest
from copilot_core.voice.control_engine import (
    VoiceControlEngine,
    VoiceIntentType,
    Language,
    create_voice_control_engine,
)


class TestVoiceControlEngine:
    """Test voice control engine."""
    
    def test_create_engine_de(self):
        """Test engine creation with German default."""
        engine = create_voice_control_engine(Language.DE)
        assert engine is not None
        assert engine._default_language == Language.DE
    
    def test_create_engine_en(self):
        """Test engine creation with English default."""
        engine = create_voice_control_engine(Language.EN)
        assert engine is not None
        assert engine._default_language == Language.EN
    
    def test_detect_turn_on_de(self):
        """Test German turn-on detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Mach das Licht an")
        assert command.intent_type == VoiceIntentType.TURN_ON
        assert command.language == Language.DE
    
    def test_detect_turn_off_de(self):
        """Test German turn-off detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Mach aus")
        assert command.intent_type == VoiceIntentType.TURN_OFF
    
    def test_detect_turn_on_en(self):
        """Test English turn-on detection."""
        engine = VoiceControlEngine(Language.EN)
        
        command = engine.process_voice_command("Turn on the light")
        assert command.intent_type == VoiceIntentType.TURN_ON
        assert command.language == Language.EN
    
    def test_detect_turn_off_en(self):
        """Test English turn-off detection."""
        engine = VoiceControlEngine(Language.EN)
        
        command = engine.process_voice_command("Turn off")
        assert command.intent_type == VoiceIntentType.TURN_OFF
    
    def test_detect_zone_living_room(self):
        """Test living room zone detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Licht im Wohnzimmer an")
        assert command.zone_id == "zone_living_room"
    
    def test_detect_zone_kitchen(self):
        """Test kitchen zone detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Küche Licht aus")
        assert command.zone_id == "zone_kitchen"
    
    def test_detect_brightness_parameter(self):
        """Test brightness parameter detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Dimmer auf 50%")
        assert command.intent_type == VoiceIntentType.DIM
        assert command.parameters.get("brightness") == 50
    
    def test_detect_temperature_parameter(self):
        """Test temperature parameter detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Heizung auf 22 Grad")
        assert "temperature" in command.parameters
    
    def test_unknown_intent(self):
        """Test unknown intent handling."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Ich möchte Pizza bestellen")
        assert command.intent_type == VoiceIntentType.UNKNOWN
    
    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        engine = VoiceControlEngine(Language.DE)
        
        # Known intent + zone = high confidence
        command1 = engine.process_voice_command("Licht im Wohnzimmer an")
        assert command1.confidence >= 0.8
        
        # Unknown intent = low confidence
        command2 = engine.process_voice_command("Was ist das")
        assert command2.confidence < 0.8
    
    def test_generate_response_de(self):
        """Test German response generation."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Licht an")
        response = engine.generate_response(command)
        
        assert response.text_de is not None
        assert len(response.text_de) > 0
        assert response.text_en is not None
    
    def test_generate_response_requires_confirmation(self):
        """Test that low confidence requires confirmation."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Was war das")  # Unknown intent
        response = engine.generate_response(command)
        
        assert response.requires_confirmation is True
    
    def test_command_history(self):
        """Test command history tracking."""
        engine = VoiceControlEngine(Language.DE)
        
        # Process multiple commands
        for i in range(5):
            engine.process_voice_command(f"Befehl {i}")
        
        history = engine.get_command_history(limit=10)
        assert len(history) == 5
    
    def test_command_history_trimming(self):
        """Test command history trimming to 100."""
        engine = VoiceControlEngine(Language.DE)
        
        # Process 150 commands
        for i in range(150):
            engine.process_voice_command(f"Befehl {i}")
        
        history = engine.get_command_history(limit=200)
        assert len(history) == 100  # Trimmed to 100
    
    def test_response_history(self):
        """Test response history tracking."""
        engine = VoiceControlEngine(Language.DE)
        
        # Process commands and generate responses
        for i in range(5):
            command = engine.process_voice_command(f"Licht an {i}")
            engine.generate_response(command)
        
        responses = engine.get_responses(limit=10)
        assert len(responses) == 5
    
    def test_set_language(self):
        """Test language switching."""
        engine = VoiceControlEngine(Language.DE)
        
        # Switch to English
        engine.set_language(Language.EN)
        assert engine._default_language == Language.EN
        
        # Next command should be English
        command = engine.process_voice_command("Turn on light")
        assert command.language == Language.EN
    
    def test_command_to_dict(self):
        """Test command serialization."""
        command = VoiceControlEngine(Language.DE).process_voice_command("Licht im Wohnzimmer an")
        
        d = command.to_dict()
        
        assert d["command_id"].startswith("voice_")
        assert d["intent_type"] == "turn_on"
        assert d["language"] == "de"
        assert d["zone_id"] == "zone_living_room"
        assert d["raw_text"] == "Licht im Wohnzimmer an"
        assert d["confidence"] > 0
    
    def test_response_to_dict(self):
        """Test response serialization."""
        engine = VoiceControlEngine(Language.DE)
        command = engine.process_voice_command("Licht an")
        response = engine.generate_response(command)
        
        d = response.to_dict()
        
        assert d["response_id"].startswith("resp_")
        assert d["command_id"] == command.command_id
        assert d["text_de"] is not None
        assert d["text_en"] is not None
        assert d["requires_confirmation"] is False or d["requires_confirmation"] is True


class TestVoiceIntentPatterns:
    """Test voice intent pattern matching."""
    
    def test_dim_detection_de(self):
        """Test German dim detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Mach es dunkler")
        assert command.intent_type == VoiceIntentType.DIM
    
    def test_brighten_detection_de(self):
        """Test German brighten detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Mach es heller")
        assert command.intent_type == VoiceIntentType.BRIGHTEN
    
    def test_status_query_detection_de(self):
        """Test German status query detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Wie ist der Status?")
        assert command.intent_type == VoiceIntentType.STATUS_QUERY
    
    def test_dim_detection_en(self):
        """Test English dim detection."""
        engine = VoiceControlEngine(Language.EN)
        
        command = engine.process_voice_command("Make it darker")
        assert command.intent_type == VoiceIntentType.DIM
    
    def test_brighten_detection_en(self):
        """Test English brighten detection."""
        engine = VoiceControlEngine(Language.EN)
        
        command = engine.process_voice_command("Brighter please")
        assert command.intent_type == VoiceIntentType.BRIGHTEN


class TestZonePatternMatching:
    """Test zone pattern matching."""
    
    def test_zone_bedroom_de(self):
        """Test German bedroom detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Licht im Schlafzimmer an")
        assert command.zone_id == "zone_bedroom"
    
    def test_zone_bathroom_de(self):
        """Test German bathroom detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Bad Licht aus")
        assert command.zone_id == "zone_bathroom"
    
    def test_zone_flur_de(self):
        """Test German hallway detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Flur beleuchten")
        assert command.zone_id == "zone_hallway"
    
    def test_zone_office_de(self):
        """Test German office detection."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Büro Licht an")
        assert command.zone_id == "zone_office"
    
    def test_no_zone_detected(self):
        """Test command without zone."""
        engine = VoiceControlEngine(Language.DE)
        
        command = engine.process_voice_command("Licht an")
        assert command.zone_id is None
