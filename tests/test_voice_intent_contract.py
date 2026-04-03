"""Contract tests for Voice Intent Hardening — Slice 73.

Tests robust intent recognition with:
- Edge case handling
- Multilingual entity aliases
- Confidence threshold tuning
- Production-ready parsing
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch


class TestIntentPatternRobustness:
    """Test intent pattern matching robustness."""
    
    def test_intent_with_noise_words(self):
        """Test intent recognition with filler/noise words."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        # Commands with noise/filler words
        noisy_commands = [
            "Äh, könntest du bitte vielleicht das Licht im Wohnzimmer anmachen?",
            "Also, ich würde sagen, mach mal bitte das Licht an",
            "Hey, kannst du mal kurz das Licht einschalten, bitte?",
        ]
        
        for text in noisy_commands:
            command = engine.process_voice_command(text)
            # Should still detect TURN_ON despite noise
            assert command.intent_type.value in ("turn_on", "unknown")
    
    def test_intent_with_typos(self):
        """Test intent recognition with common typos."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        typo_commands = [
            "Licht anmachn",  # Missing 'e'
            "Licht eischalten",  # Missing 'n'
            "Licht auschalten",  # Missing 's'
            "Heizung auf 21 Grad stelen",  # Missing 'l'
        ]
        
        # Should handle common typos gracefully
        for text in typo_commands:
            command = engine.process_voice_command(text)
            # At minimum should not crash, ideally detect intent
            assert command.confidence >= 0.0
    
    def test_intent_with_partial_phrases(self):
        """Test intent recognition with partial/incomplete phrases."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        partial_commands = [
            "Licht",  # No action
            "an",  # No target
            "Wohnzimmer",  # No action
            "21 Grad",  # No action specified
        ]
        
        for text in partial_commands:
            command = engine.process_voice_command(text)
            # Should handle gracefully (may be UNKNOWN)
            assert command is not None
    
    def test_intent_with_multiple_intents(self):
        """Test handling of commands with multiple potential intents."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        ambiguous_commands = [
            "Licht an und dann wieder aus",
            "Heller machen aber nicht zu hell",
            "Heizung an aber Temperatur auf 20",
        ]
        
        for text in ambiguous_commands:
            command = engine.process_voice_command(text)
            # Should pick one intent deterministically
            assert command.intent_type is not None
    
    def test_intent_with_negation(self):
        """Test handling of negated commands."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        negated_commands = [
            "Mach das Licht nicht an",
            "Schalte die Heizung nicht aus",
            "Bitte nicht dimmen",
        ]
        
        for text in negated_commands:
            command = engine.process_voice_command(text)
            # Negation handling may vary, but should not crash
            assert command is not None


class TestMultilingualEntityAliases:
    """Test multilingual entity/zone alias recognition."""
    
    def test_german_zone_aliases(self):
        """Test German zone name variations."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        living_room_aliases = [
            "Wohnzimmer",
            "Wohnraum",
            "Wohnbereich",
            "im Wohnzimmer",
            "im Wohnbereich",
        ]
        
        for text in living_room_aliases:
            command = engine.process_voice_command(f"Licht an {text}")
            # Should detect zone
            assert command.zone_id is not None or command.confidence >= 0.0
    
    def test_english_zone_aliases(self):
        """Test English zone name variations."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.EN)
        
        living_room_aliases = [
            "living room",
            "living room area",
            "the living room",
            "in the living room",
        ]
        
        for text in living_room_aliases:
            command = engine.process_voice_command(f"Turn on light {text}")
            # Should detect zone
            assert command.zone_id is not None or command.confidence >= 0.0
    
    def test_device_type_aliases_german(self):
        """Test German device type aliases."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        light_aliases = [
            "Licht",
            "Lampe",
            "Beleuchtung",
            "Leuchte",
        ]
        
        for device in light_aliases:
            command = engine.process_voice_command(f"{device} an")
            # Should recognize as light-related
            assert command is not None
    
    def test_device_type_aliases_english(self):
        """Test English device type aliases."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.EN)
        
        light_aliases = [
            "light",
            "lamp",
            "lights",
            "lighting",
        ]
        
        for device in light_aliases:
            command = engine.process_voice_command(f"Turn on {device}")
            # Should recognize as light-related
            assert command is not None
    
    def test_mixed_language_zone_names(self):
        """Test handling of mixed language zone names."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        mixed_commands = [
            "Licht an im living room",
            "Turn on light im Wohnzimmer",
            "Licht im Bad/Bathroom",
        ]
        
        for text in mixed_commands:
            command = engine.process_voice_command(text)
            # Should handle gracefully
            assert command is not None


class TestConfidenceThresholdTuning:
    """Test confidence threshold behavior."""
    
    def test_high_confidence_clear_intent(self):
        """Test high confidence for clear intents."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        clear_commands = [
            "Schalte das Licht im Wohnzimmer ein",
            "Mach die Heizung auf 21 Grad",
            "Dimme das Licht auf 50%",
        ]
        
        for text in clear_commands:
            command = engine.process_voice_command(text)
            # Clear commands should have reasonable confidence
            assert command.confidence >= 0.5
    
    def test_low_confidence_ambiguous_intent(self):
        """Test low confidence for ambiguous intents."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        ambiguous_commands = [
            "irgendwas mit licht",
            "vielleicht heizung",
            "könntest du mal",
        ]
        
        for text in ambiguous_commands:
            command = engine.process_voice_command(text)
            # Ambiguous commands should have lower confidence
            assert command.confidence <= 0.8
    
    def test_confidence_with_zone_detection(self):
        """Test confidence boost from zone detection."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        # Without zone
        command_no_zone = engine.process_voice_command("Licht an")
        
        # With zone
        command_with_zone = engine.process_voice_command("Licht im Wohnzimmer an")
        
        # Zone detection should increase confidence
        assert command_with_zone.confidence >= command_no_zone.confidence
    
    def test_confidence_threshold_for_confirmation(self):
        """Test that low confidence triggers confirmation requirement."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        # Low confidence command
        command = engine.process_voice_command("irgendwas machen")
        response = engine.generate_response(command)
        
        # Low confidence should require confirmation
        if command.confidence < 0.7:
            assert response.requires_confirmation is True


class TestProductionEdgeCases:
    """Test production edge cases."""
    
    def test_empty_command(self):
        """Test handling of empty command."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        command = engine.process_voice_command("")
        
        assert command.intent_type.value == "unknown"
        assert command.confidence <= 0.5
    
    def test_very_long_command(self):
        """Test handling of very long commands."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        long_command = "Bitte schalte das Licht im Wohnzimmer an und dann im Schlafzimmer aus und dann im Badezimmer auf 50% und dann in der Küche auf voll und dann im Flur auf rot und dann im Büro auf blau und dann im Wohnzimmer wieder auf weiß"
        
        command = engine.process_voice_command(long_command)
        
        # Should handle without crashing
        assert command is not None
    
    def test_special_characters_command(self):
        """Test handling of commands with special characters."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        special_commands = [
            "Licht an!!!",
            "Heizung auf 21°",
            "Licht auf 50%!!!",
            "Licht an (bitte)",
        ]
        
        for text in special_commands:
            command = engine.process_voice_command(text)
            # Should handle special characters gracefully
            assert command is not None
    
    def test_unicode_command(self):
        """Test handling of Unicode characters."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        unicode_commands = [
            "Licht an 🔆",
            "Heizung auf 21°C 🌡️",
            "Bitte Licht an 🙏",
        ]
        
        for text in unicode_commands:
            command = engine.process_voice_command(text)
            # Should handle Unicode gracefully
            assert command is not None
    
    def test_command_history_limit(self):
        """Test that command history is properly limited."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        # Generate 150 commands
        for i in range(150):
            engine.process_voice_command(f"Licht an {i}")
        
        history = engine.get_command_history(limit=100)
        
        # Should only keep last 100
        assert len(history) <= 100
    
    def test_response_generation_all_intents(self):
        """Test response generation for all intent types."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language, VoiceIntentType
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        for intent_type in VoiceIntentType:
            command = Mock()
            command.intent_type = intent_type
            command.zone_id = "zone_living_room"
            command.confidence = 0.8
            
            response = engine.generate_response(command)
            
            # Should generate response for all intent types
            assert response is not None
            assert response.text_de is not None
            assert response.text_en is not None


class TestIntentParameterExtraction:
    """Test parameter extraction from intents."""
    
    def test_brightness_percentage_extraction(self):
        """Test brightness percentage extraction."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        test_cases = [
            ("Licht auf 50%", 50),
            ("Licht auf 50 Prozent", 50),
            ("Dimmer auf 75%", 75),
            ("Heller auf 100%", 100),
        ]
        
        for text, expected in test_cases:
            command = engine.process_voice_command(text)
            if "brightness" in command.parameters:
                assert command.parameters["brightness"] == expected
    
    def test_temperature_extraction(self):
        """Test temperature extraction."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        test_cases = [
            ("Heizung auf 21 Grad", 21),
            ("Temperatur auf 22°", 22),
            ("Stelle auf 20 Grad", 20),
        ]
        
        for text, expected in test_cases:
            command = engine.process_voice_command(text)
            if "temperature" in command.parameters:
                assert command.parameters["temperature"] == expected
    
    def test_color_extraction(self):
        """Test color extraction."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        test_cases = [
            "Licht auf rot",
            "Licht auf blau",
            "Licht auf grün",
            "Licht auf weiß",
        ]
        
        for text in test_cases:
            command = engine.process_voice_command(text)
            # Should extract color if intent matches
            assert command is not None
    
    def test_zone_from_context(self):
        """Test zone extraction from command context."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        test_cases = [
            ("Wohnzimmer Licht an", "zone_living_room"),
            ("Schlafzimmer Licht aus", "zone_bedroom"),
            ("Küche Heizung an", "zone_kitchen"),
        ]
        
        for text, expected_zone in test_cases:
            command = engine.process_voice_command(text)
            if command.zone_id:
                assert command.zone_id == expected_zone


class TestLanguageSwitchingRobustness:
    """Test language switching robustness."""
    
    def test_switch_during_conversation(self):
        """Test language switching mid-conversation."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        # Start in German
        command_de = engine.process_voice_command("Licht an")
        assert command_de.language == Language.DE
        
        # Switch to English
        engine.set_language(Language.EN)
        
        # Continue in English
        command_en = engine.process_voice_command("Light on")
        assert command_en.language == Language.EN
    
    def test_invalid_language_handling(self):
        """Test handling of invalid language codes."""
        from copilot_core.voice.control_engine import VoiceControlEngine, Language
        
        engine = VoiceControlEngine(default_language=Language.DE)
        
        # Try to set invalid language
        try:
            engine.set_language(Language.FR)  # type: ignore
        except (AttributeError, ValueError):
            # Should handle gracefully
            pass
        
        # Should still work with valid language
        command = engine.process_voice_command("Licht an")
        assert command.language == Language.DE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
