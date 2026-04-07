"""Multilingual Voice Intent Parsing and Response Generation.

Extended DE/EN support for voice intents with:
- Language detection and switching
- Bilingual intent patterns
- Translation quality testing
- Cross-language response generation
- Locale-aware formatting

Features:
- Automatische Spracherkennung (DE/EN)
- Sprachumschaltung zur Laufzeit
- Zweisprachige Intent-Patterns
- Lokalisierungs-aware Antwortgenerierung
- Übersetzungsqualitätstests
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .voice_handler import VoiceIntent, VoiceResponse, IntentType, VoiceIntentHandler
from .context_builder import VoiceContext

_LOGGER = logging.getLogger(__name__)


class LanguageCode(str, Enum):
    """Supported language codes."""
    DE = "de"
    EN = "en"


@dataclass
class LanguagePreference:
    """User language preference settings."""
    
    primary_language: LanguageCode = LanguageCode.DE
    secondary_language: Optional[LanguageCode] = None
    auto_detect: bool = True
    fallback_to_primary: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_language": self.primary_language.value,
            "secondary_language": self.secondary_language.value if self.secondary_language else None,
            "auto_detect": self.auto_detect,
            "fallback_to_primary": self.fallback_to_primary,
        }


@dataclass
class TranslationQualityMetrics:
    """Metrics for translation quality tracking."""
    
    total_translations: int = 0
    successful_translations: int = 0
    failed_translations: int = 0
    avg_confidence: float = 0.0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_translations": self.total_translations,
            "successful_translations": self.successful_translations,
            "failed_translations": self.failed_translations,
            "success_rate": (
                self.successful_translations / max(1, self.total_translations)
            ),
            "avg_confidence": self.avg_confidence,
            "last_error": self.last_error,
        }


class MultilingualVoiceHandler(VoiceIntentHandler):
    """Extended voice handler with full multilingual support.
    
    Extends VoiceIntentHandler with:
    - Enhanced language detection
    - Dynamic language switching
    - Bilingual response generation
    - Translation quality tracking
    """
    
    # Enhanced language detection patterns
    DE_LANGUAGE_INDICATORS = [
        "bitte", "danke", "können", "könnte", "würde", "hätte",
        "möchte", "sollte", "müsste", "gerne", "vielleicht",
        "eigentlich", "wirklich", "sehr", "auch", "noch", "schon",
        "nicht", "kein", "keine", "keiner", "keines",
        "der", "die", "das", "den", "dem", "des",
        "und", "oder", "aber", "denn", "weil", "wenn", "als",
        "ist", "sind", "war", "waren", "sein", "haben", "hatte",
        "machen", "mach", "licht", "an", "aus",
    ]
    
    EN_LANGUAGE_INDICATORS = [
        "please", "thank", "thanks", "could", "would", "should",
        "might", "want", "like", "maybe", "perhaps",
        "actually", "really", "very", "also", "still", "already",
        "not", "no", "none", "neither",
        "the", "a", "an", "and", "or", "but", "because", "if", "when",
        "is", "are", "was", "were", "be", "have", "had",
        "make", "do", "light", "on", "off",
    ]
    
    # Confidence thresholds for language detection
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    LOW_CONFIDENCE_THRESHOLD = 0.5
    
    def __init__(
        self,
        mood_engine: Optional[Any] = None,
        habitus_service: Optional[Any] = None,
        default_language: str = "de",
        language_preference: Optional[LanguagePreference] = None,
        bilingual_mode: bool = False,
    ):
        """Initialize multilingual voice handler.
        
        Args:
            mood_engine: Mood engine for context-aware responses
            habitus_service: Habitus service for pattern-based suggestions
            default_language: Default language (de/en)
            language_preference: User language preferences
            bilingual_mode: Enable bilingual response generation
        """
        super().__init__(
            mood_engine=mood_engine,
            habitus_service=habitus_service,
            default_language=default_language,
        )
        
        self.language_preference = language_preference or LanguagePreference()
        self._translation_metrics = TranslationQualityMetrics()
        self._current_language: Optional[LanguageCode] = None
        self._bilingual_mode = bilingual_mode
    
    def detect_language(self, text: str) -> Tuple[LanguageCode, float]:
        """Detect language from text with confidence score.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Tuple of (detected_language, confidence_score)
        """
        text_lower = text.lower()
        
        # Count language indicators
        de_count = sum(1 for word in self.DE_LANGUAGE_INDICATORS if word in text_lower)
        en_count = sum(1 for word in self.EN_LANGUAGE_INDICATORS if word in text_lower)
        
        total_indicators = de_count + en_count
        
        # Update metrics
        self._translation_metrics.total_translations += 1
        
        if total_indicators == 0:
            # No clear indicators - use default
            self._translation_metrics.avg_confidence = 0.5
            return (
                LanguageCode(self.default_language),
                0.5  # Neutral confidence
            )
        
        # Calculate confidence
        if de_count > en_count:
            confidence = de_count / total_indicators
            detected = LanguageCode.DE
        elif en_count > de_count:
            confidence = en_count / total_indicators
            detected = LanguageCode.EN
        else:
            # Tie - use default language
            detected = LanguageCode(self.default_language)
            confidence = 0.5
        
        # Update metrics
        self._translation_metrics.avg_confidence = (
            (self._translation_metrics.avg_confidence * (self._translation_metrics.total_translations - 1) + confidence)
            / self._translation_metrics.total_translations
        )
        
        return detected, round(confidence, 2)
    
    def parse_intent(
        self,
        text: str,
        language: Optional[str] = None,
    ) -> VoiceIntent:
        """Parse voice text into structured intent with language detection.
        
        Args:
            text: Voice input text
            language: Language code (de/en), auto-detected if None
            
        Returns:
            Parsed VoiceIntent with detected language
        """
        # Auto-detect language if not provided
        if language is None and self.language_preference.auto_detect:
            detected_lang, confidence = self.detect_language(text)
            
            # Use detected language if confidence is high enough
            if confidence >= self.LOW_CONFIDENCE_THRESHOLD:
                language = detected_lang.value
                self._current_language = detected_lang
            else:
                # Fall back to primary language
                language = self.language_preference.primary_language.value
                self._current_language = self.language_preference.primary_language
        else:
            # Use provided or default language
            language = language or self.default_language
            self._current_language = LanguageCode(language)
        
        # Parse with detected language
        return super().parse_intent(text, language)
    
    def handle_intent(
        self,
        intent: VoiceIntent,
        context: Optional[VoiceContext] = None,
    ) -> VoiceResponse:
        """Handle parsed intent with multilingual response generation.
        
        Args:
            intent: Parsed voice intent
            context: Current voice context
            
        Returns:
            VoiceResponse in appropriate language
        """
        # Ensure intent has correct language
        if intent.language not in ("de", "en"):
            intent.language = self._current_language.value if self._current_language else self.default_language
        
        response = super().handle_intent(intent, context)
        
        # Ensure response language matches intent
        response.language = intent.language
        
        return response
    
    def switch_language(self, language: str) -> bool:
        """Switch to a different language.
        
        Args:
            language: Target language code (de/en)
            
        Returns:
            True if switch successful, False otherwise
        """
        try:
            lang_code = LanguageCode(language)
            
            # Validate language is supported
            if lang_code == self.language_preference.primary_language or \
               lang_code == self.language_preference.secondary_language or \
               language in ("de", "en"):
                self.default_language = language
                self._current_language = lang_code
                _LOGGER.info("Language switched to %s", language)
                return True
            
            _LOGGER.warning("Unsupported language: %s", language)
            return False
        
        except ValueError:
            _LOGGER.warning("Invalid language code: %s", language)
            return False
    
    def get_translation_metrics(self) -> TranslationQualityMetrics:
        """Get current translation quality metrics."""
        return self._translation_metrics
    
    def reset_translation_metrics(self):
        """Reset translation quality metrics."""
        self._translation_metrics = TranslationQualityMetrics()
    
    def generate_bilingual_response(
        self,
        intent: VoiceIntent,
        context: Optional[VoiceContext] = None,
    ) -> VoiceResponse:
        """Generate response in both primary and secondary languages.
        
        Args:
            intent: Parsed voice intent
            context: Current voice context
            
        Returns:
            VoiceResponse with bilingual text
        """
        # Generate in primary language
        intent.language = self.language_preference.primary_language.value
        primary_response = self.handle_intent(intent, context)
        
        # Generate in secondary language if available
        secondary_text = None
        if self.language_preference.secondary_language:
            intent.language = self.language_preference.secondary_language.value
            secondary_response = self.handle_intent(intent, context)
            secondary_text = secondary_response.tts_text
        
        # Combine responses
        if secondary_text:
            primary_response.tts_text = f"{primary_response.tts_text} / {secondary_text}"
        
        # Reset to detected language
        intent.language = self._current_language.value if self._current_language else self.default_language
        
        return primary_response


class MultilingualResponseGenerator:
    """Generates localized responses for voice intents.
    
    Provides:
    - Template-based response generation
    - Locale-aware number/date formatting
    - Cross-language response variants
    """
    
    # Response templates (DE)
    DE_TEMPLATES = {
        IntentType.LIGHT_ON: "Licht ist eingeschaltet.",
        IntentType.LIGHT_OFF: "Licht ist ausgeschaltet.",
        IntentType.CLIMATE_SET: "Temperatur ist auf {temperature}°C eingestellt.",
        IntentType.MEDIA_PLAY: "Spiele Musik.",
        IntentType.MEDIA_PAUSE: "Pause.",
        IntentType.MEDIA_STOP: "Stopp.",
        IntentType.STATUS_QUERY: "Status: {status}",
        IntentType.TIME_QUERY: "Es ist {time} Uhr.",
        IntentType.UNKNOWN: "Ich habe dich nicht verstanden. Kannst du das bitte wiederholen?",
    }
    
    # Response templates (EN)
    EN_TEMPLATES = {
        IntentType.LIGHT_ON: "Light is turned on.",
        IntentType.LIGHT_OFF: "Light is turned off.",
        IntentType.CLIMATE_SET: "Temperature is set to {temperature}°C.",
        IntentType.MEDIA_PLAY: "Playing music.",
        IntentType.MEDIA_PAUSE: "Paused.",
        IntentType.MEDIA_STOP: "Stopped.",
        IntentType.STATUS_QUERY: "Status: {status}",
        IntentType.TIME_QUERY: "It's {time}.",
        IntentType.UNKNOWN: "I didn't understand. Could you repeat that?",
    }
    
    def __init__(self, default_language: str = "de"):
        """Initialize response generator.
        
        Args:
            default_language: Default language for responses
        """
        self.default_language = default_language
    
    def generate_response(
        self,
        intent_type: IntentType,
        language: str = "de",
        **kwargs,
    ) -> str:
        """Generate localized response for intent type.
        
        Args:
            intent_type: Type of intent
            language: Language code (de/en)
            **kwargs: Template parameters
            
        Returns:
            Localized response string
        """
        templates = self.DE_TEMPLATES if language == "de" else self.EN_TEMPLATES
        template = templates.get(intent_type, templates[IntentType.UNKNOWN])
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            _LOGGER.warning("Missing template parameter: %s", e)
            return template
    
    def format_time(self, time: datetime, language: str = "de") -> str:
        """Format time in locale-aware way.
        
        Args:
            time: Time to format
            language: Language code
            
        Returns:
            Formatted time string
        """
        if language == "de":
            return time.strftime("%H:%M")
        else:
            return time.strftime("%I:%M %p")
    
    def format_temperature(self, temperature: float, language: str = "de") -> str:
        """Format temperature in locale-aware way.
        
        Args:
            temperature: Temperature value
            language: Language code
            
        Returns:
            Formatted temperature string
        """
        if language == "de":
            return f"{temperature:.1f}°C"
        else:
            # Convert to Fahrenheit for English
            fahrenheit = temperature * 9/5 + 32
            return f"{fahrenheit:.1f}°F"


@dataclass
class MultilingualVoiceConfig:
    """Configuration for multilingual voice support."""
    
    supported_languages: List[LanguageCode] = field(default_factory=lambda: [LanguageCode.DE, LanguageCode.EN])
    default_language: LanguageCode = LanguageCode.DE
    auto_detect_enabled: bool = True
    fallback_enabled: bool = True
    bilingual_mode: bool = False
    quality_tracking_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "supported_languages": [lang.value for lang in self.supported_languages],
            "default_language": self.default_language.value,
            "auto_detect_enabled": self.auto_detect_enabled,
            "fallback_enabled": self.fallback_enabled,
            "bilingual_mode": self.bilingual_mode,
            "quality_tracking_enabled": self.quality_tracking_enabled,
        }
