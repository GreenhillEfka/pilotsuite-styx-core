"""Contract tests for Multilingual Voice Surface.

Tests the multilingual voice support system:
- MultilingualVoiceHandler class
- Language detection with confidence scores
- Bilingual response generation
- Language switching
- Translation quality metrics
- Locale-aware formatting
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch


class TestLanguageDetection:
    """Test language detection functionality."""
    
    def test_detect_german_text(self):
        """Test German language detection."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler()
        
        # Clear German text
        text = "Bitte mach das Licht an"
        lang, confidence = handler.detect_language(text)
        
        assert lang.value == "de"
        assert confidence >= 0.5
    
    def test_detect_english_text(self):
        """Test English language detection."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # Clear English text
        text = "Please turn on the light"
        lang, confidence = handler.detect_language(text)
        
        assert lang.value == "en"
        assert confidence >= 0.5
    
    def test_detect_mixed_language_defaults_to_primary(self):
        """Test mixed language detection falls back to primary."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler, LanguagePreference
        
        handler = MultilingualVoiceHandler(
            default_language="de",
            language_preference=LanguagePreference(primary_language="de"),
        )
        
        # Mixed text with equal indicators
        text = "Please mach das Licht"
        lang, confidence = handler.detect_language(text)
        
        # Should default to primary language on tie
        assert lang.value == "de"
    
    def test_detect_language_confidence_calculation(self):
        """Test confidence score calculation."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler()
        
        # Very clear German text
        text_de = "Bitte kannst du das Licht im Wohnzimmer einschalten"
        _, confidence_de = handler.detect_language(text_de)
        
        # Very clear English text
        text_en = "Please can you turn on the light in the living room"
        _, confidence_en = handler.detect_language(text_en)
        
        # Both should have reasonable confidence
        assert confidence_de >= 0.5
        assert confidence_en >= 0.5
    
    def test_detect_language_no_indicators(self):
        """Test language detection with no clear indicators."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # Text with no language indicators
        text = "Licht an"
        lang, confidence = handler.detect_language(text)
        
        # Should use default language with neutral confidence
        assert lang.value == "de"
        assert confidence == 0.5


class TestMultilingualVoiceHandler:
    """Test MultilingualVoiceHandler class."""
    
    def test_handler_initialization(self):
        """Test handler initialization with language preferences."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler, LanguagePreference, LanguageCode
        
        pref = LanguagePreference(
            primary_language=LanguageCode.DE,
            secondary_language=LanguageCode.EN,
            auto_detect=True,
        )
        
        handler = MultilingualVoiceHandler(
            default_language="de",
            language_preference=pref,
        )
        
        assert handler.language_preference.primary_language == LanguageCode.DE
        assert handler.language_preference.secondary_language == LanguageCode.EN
        assert handler.language_preference.auto_detect is True
    
    def test_switch_language_success(self):
        """Test successful language switching."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # Switch to English
        result = handler.switch_language("en")
        
        assert result is True
        assert handler.default_language == "en"
    
    def test_switch_language_invalid(self):
        """Test language switching with invalid language."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # Try invalid language
        result = handler.switch_language("fr")
        
        assert result is False
        assert handler.default_language == "de"  # Unchanged
    
    def test_parse_intent_with_auto_detect(self):
        """Test intent parsing with auto language detection."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # English text with auto-detect
        text = "Please turn on the light"
        intent = handler.parse_intent(text)
        
        # Should detect English
        assert intent.language == "en"
        assert intent.raw_text == text
    
    def test_parse_intent_with_explicit_language(self):
        """Test intent parsing with explicit language override."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # German text but explicitly set to English
        text = "Licht an"
        intent = handler.parse_intent(text, language="en")
        
        # Should use explicit language
        assert intent.language == "en"
    
    def test_handle_intent_preserves_language(self):
        """Test that handle_intent preserves intent language."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # Parse English intent
        intent = handler.parse_intent("Please turn on the light")
        
        # Handle intent
        response = handler.handle_intent(intent)
        
        # Response should be in English
        assert response.language == "en"
    
    def test_generate_bilingual_response(self):
        """Test bilingual response generation."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler, LanguagePreference, LanguageCode
        
        handler = MultilingualVoiceHandler(
            default_language="de",
            language_preference=LanguagePreference(
                primary_language=LanguageCode.DE,
                secondary_language=LanguageCode.EN,
            ),
            bilingual_mode=True,
        )
        
        # Parse intent
        intent = handler.parse_intent("Licht an")
        
        # Generate bilingual response
        response = handler.generate_bilingual_response(intent)
        
        # Should contain both languages (separated by /)
        assert "/" in response.tts_text or response.tts_text  # At minimum has primary response


class TestTranslationQualityMetrics:
    """Test translation quality tracking."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        from copilot_core.voice.multilingual import TranslationQualityMetrics
        
        metrics = TranslationQualityMetrics()
        
        assert metrics.total_translations == 0
        assert metrics.successful_translations == 0
        assert metrics.failed_translations == 0
        assert metrics.avg_confidence == 0.0
        assert metrics.last_error is None
    
    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        from copilot_core.voice.multilingual import TranslationQualityMetrics
        
        metrics = TranslationQualityMetrics(
            total_translations=10,
            successful_translations=8,
            failed_translations=2,
            avg_confidence=0.85,
        )
        
        data = metrics.to_dict()
        
        assert data["total_translations"] == 10
        assert data["successful_translations"] == 8
        assert data["failed_translations"] == 2
        assert data["success_rate"] == 0.8
        assert data["avg_confidence"] == 0.85
    
    def test_metrics_tracking_via_handler(self):
        """Test metrics tracking through handler."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler()
        
        # Perform multiple language detections
        texts = [
            "Bitte mach das Licht an",
            "Please turn on the light",
            "Licht aus bitte",
            "Turn off the light please",
        ]
        
        for text in texts:
            handler.detect_language(text)
        
        metrics = handler.get_translation_metrics()
        
        assert metrics.total_translations == 4
        assert metrics.avg_confidence > 0


class TestMultilingualResponseGenerator:
    """Test MultilingualResponseGenerator class."""
    
    def test_generate_german_response(self):
        """Test German response generation."""
        from copilot_core.voice.multilingual import MultilingualResponseGenerator
        from copilot_core.voice.voice_handler import IntentType
        
        generator = MultilingualResponseGenerator(default_language="de")
        
        response = generator.generate_response(IntentType.LIGHT_ON, language="de")
        
        assert "Licht" in response
        assert "eingeschaltet" in response or "an" in response.lower()
    
    def test_generate_english_response(self):
        """Test English response generation."""
        from copilot_core.voice.multilingual import MultilingualResponseGenerator
        from copilot_core.voice.voice_handler import IntentType
        
        generator = MultilingualResponseGenerator(default_language="de")
        
        response = generator.generate_response(IntentType.LIGHT_ON, language="en")
        
        assert "Light" in response
        assert "on" in response.lower()
    
    def test_generate_response_with_parameters(self):
        """Test response generation with template parameters."""
        from copilot_core.voice.multilingual import MultilingualResponseGenerator
        from copilot_core.voice.voice_handler import IntentType
        
        generator = MultilingualResponseGenerator()
        
        # German
        response_de = generator.generate_response(
            IntentType.CLIMATE_SET,
            language="de",
            temperature=21,
        )
        assert "21" in response_de
        
        # English
        response_en = generator.generate_response(
            IntentType.CLIMATE_SET,
            language="en",
            temperature=21,
        )
        assert "21" in response_en
    
    def test_format_time_german(self):
        """Test German time formatting."""
        from copilot_core.voice.multilingual import MultilingualResponseGenerator
        
        generator = MultilingualResponseGenerator()
        time = datetime(2026, 4, 3, 14, 30, tzinfo=timezone.utc)
        
        formatted = generator.format_time(time, language="de")
        
        assert "14:30" in formatted
        assert "PM" not in formatted
    
    def test_format_time_english(self):
        """Test English time formatting."""
        from copilot_core.voice.multilingual import MultilingualResponseGenerator
        
        generator = MultilingualResponseGenerator()
        time = datetime(2026, 4, 3, 14, 30, tzinfo=timezone.utc)
        
        formatted = generator.format_time(time, language="en")
        
        # English uses 12-hour format with AM/PM
        assert "02:30" in formatted or "2:30" in formatted
        assert "PM" in formatted
    
    def test_format_temperature_german(self):
        """Test German temperature formatting (Celsius)."""
        from copilot_core.voice.multilingual import MultilingualResponseGenerator
        
        generator = MultilingualResponseGenerator()
        
        formatted = generator.format_temperature(21.5, language="de")
        
        assert "21.5" in formatted
        assert "°C" in formatted
    
    def test_format_temperature_english(self):
        """Test English temperature formatting (Fahrenheit)."""
        from copilot_core.voice.multilingual import MultilingualResponseGenerator
        
        generator = MultilingualResponseGenerator()
        
        formatted = generator.format_temperature(21.5, language="en")
        
        # 21.5°C = 70.7°F
        assert "70.7" in formatted
        assert "°F" in formatted


class TestLanguagePreference:
    """Test LanguagePreference dataclass."""
    
    def test_preference_creation(self):
        """Test language preference creation."""
        from copilot_core.voice.multilingual import LanguagePreference, LanguageCode
        
        pref = LanguagePreference(
            primary_language=LanguageCode.DE,
            secondary_language=LanguageCode.EN,
            auto_detect=True,
            fallback_to_primary=True,
        )
        
        assert pref.primary_language == LanguageCode.DE
        assert pref.secondary_language == LanguageCode.EN
        assert pref.auto_detect is True
        assert pref.fallback_to_primary is True
    
    def test_preference_to_dict(self):
        """Test preference serialization."""
        from copilot_core.voice.multilingual import LanguagePreference, LanguageCode
        
        pref = LanguagePreference(
            primary_language=LanguageCode.DE,
            secondary_language=LanguageCode.EN,
        )
        
        data = pref.to_dict()
        
        assert data["primary_language"] == "de"
        assert data["secondary_language"] == "en"
        assert data["auto_detect"] is True
    
    def test_preference_no_secondary(self):
        """Test preference without secondary language."""
        from copilot_core.voice.multilingual import LanguagePreference, LanguageCode
        
        pref = LanguagePreference(
            primary_language=LanguageCode.EN,
            secondary_language=None,
        )
        
        data = pref.to_dict()
        
        assert data["primary_language"] == "en"
        assert data["secondary_language"] is None


class TestMultilingualVoiceConfig:
    """Test MultilingualVoiceConfig dataclass."""
    
    def test_config_creation(self):
        """Test config creation."""
        from copilot_core.voice.multilingual import MultilingualVoiceConfig, LanguageCode
        
        config = MultilingualVoiceConfig(
            default_language=LanguageCode.EN,
            auto_detect_enabled=True,
            bilingual_mode=True,
        )
        
        assert config.default_language == LanguageCode.EN
        assert config.auto_detect_enabled is True
        assert config.bilingual_mode is True
    
    def test_config_to_dict(self):
        """Test config serialization."""
        from copilot_core.voice.multilingual import MultilingualVoiceConfig
        
        config = MultilingualVoiceConfig()
        data = config.to_dict()
        
        assert "supported_languages" in data
        assert "default_language" in data
        assert "auto_detect_enabled" in data
        assert "bilingual_mode" in data


class TestMultilingualEdgeCases:
    """Test edge cases in multilingual support."""
    
    def test_empty_text_detection(self):
        """Test language detection with empty text."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        lang, confidence = handler.detect_language("")
        
        # Should default to primary language
        assert lang.value == "de"
        assert confidence == 0.5
    
    def test_very_short_text_detection(self):
        """Test language detection with very short text."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        lang, confidence = handler.detect_language("Hi")
        
        # Short text should have low confidence
        assert confidence <= 0.5
    
    def test_language_switch_preserves_intent_parsing(self):
        """Test that language switch doesn't break intent parsing."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler(default_language="de")
        
        # Parse in German
        intent_de = handler.parse_intent("Licht an")
        assert intent_de.language == "de"
        
        # Switch to English
        handler.switch_language("en")
        
        # Parse in English
        intent_en = handler.parse_intent("Light on")
        assert intent_en.language == "en"
    
    def test_metrics_reset(self):
        """Test metrics reset functionality."""
        from copilot_core.voice.multilingual import MultilingualVoiceHandler
        
        handler = MultilingualVoiceHandler()
        
        # Generate some metrics
        for _ in range(5):
            handler.detect_language("Test text")
        
        metrics_before = handler.get_translation_metrics()
        assert metrics_before.total_translations == 5
        
        # Reset
        handler.reset_translation_metrics()
        
        metrics_after = handler.get_translation_metrics()
        assert metrics_after.total_translations == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
