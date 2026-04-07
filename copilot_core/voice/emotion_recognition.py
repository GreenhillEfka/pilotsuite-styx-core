"""Voice Emotion Recognition — Pitch, Intensity, Sentiment, Tone Analysis."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import time
import math

logger = logging.getLogger(__name__)


class Emotion(Enum):
    """Detected emotions."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    EXCITED = "excited"
    CALM = "calm"


@dataclass
class EmotionResult:
    """Emotion analysis result."""
    primary_emotion: Emotion
    confidence: float
    scores: Dict[Emotion, float]
    pitch_avg: float
    intensity_avg: float
    speech_rate: float
    timestamp: float = field(default_factory=lambda: time.time())


class VoiceEmotionEngine:
    """Analyzes voice signals for emotional content and sentiment."""

    def __init__(self):
        self._emotion_history: List[EmotionResult] = []
        self._baseline_pitch: float = 120.0  # Hz
        self._baseline_intensity: float = 65.0  # dB

    def analyze_audio(self, audio_data: Any, sample_rate: int = 16000) -> EmotionResult:
        """Analyze raw audio data for emotions."""
        logger.info("Analyzing voice emotion...")
        
        # Simulated feature extraction
        # In production, would use librosa/opensmile
        pitch = self._estimate_pitch(audio_data)
        intensity = self._estimate_intensity(audio_data)
        rate = 150.0  # words per minute
        
        # Calculate emotion scores
        scores = self._calculate_emotion_scores(pitch, intensity, rate)
        
        # Find primary emotion
        primary = max(scores.items(), key=lambda x: x[1])[0]
        confidence = scores[primary]
        
        result = EmotionResult(
            primary_emotion=primary,
            confidence=confidence,
            scores=scores,
            pitch_avg=pitch,
            intensity_avg=intensity,
            speech_rate=rate,
        )
        
        self._emotion_history.append(result)
        logger.info(f"Detected emotion: {primary.value} ({confidence:.2f})")
        
        return result

    def _estimate_pitch(self, audio_data: Any) -> float:
        """Estimate average pitch (Hz)."""
        # Simulated pitch estimation
        return 135.0

    def _estimate_intensity(self, audio_data: Any) -> float:
        """Estimate average intensity (dB)."""
        # Simulated intensity estimation
        return 68.0

    def _calculate_emotion_scores(self, pitch: float, intensity: float, rate: float) -> Dict[Emotion, float]:
        """Calculate scores for each emotion based on prosody."""
        scores = {e: 0.1 for e in Emotion}
        
        # Simple heuristic rules
        pitch_diff = pitch - self._baseline_pitch
        intensity_diff = intensity - self._baseline_intensity
        
        if pitch_diff > 30 and intensity_diff > 10:
            scores[Emotion.ANGRY] = 0.8
            scores[Emotion.EXCITED] = 0.7
        elif pitch_diff < -10 and intensity_diff < -5:
            scores[Emotion.SAD] = 0.75
            scores[Emotion.CALM] = 0.6
        elif pitch_diff > 15 and intensity_diff > 5:
            scores[Emotion.HAPPY] = 0.85
        else:
            scores[Emotion.NEUTRAL] = 0.9
            
        # Normalize
        total = sum(scores.values())
        return {e: s / total for e, s in scores.items()}

    def get_sentiment_score(self, text: str) -> float:
        """Calculate sentiment score from text (-1.0 to 1.0)."""
        # Simple sentiment mapping
        positive_words = ["gut", "toll", "super", "ja", "gerne", "danke", "good", "great", "yes", "thanks"]
        negative_words = ["schlecht", "nein", "falsch", "doof", "ärgerlich", "bad", "no", "wrong", "annoying"]
        
        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count + neg_count == 0:
            return 0.0
        
        return (pos_count - neg_count) / (pos_count + neg_count)

    def get_user_mood(self, window_size: int = 5) -> Optional[Emotion]:
        """Get average user mood over last N interactions."""
        if not self._emotion_history:
            return None
            
        recent = self._emotion_history[-window_size:]
        counts = {}
        for res in recent:
            counts[res.primary_emotion] = counts.get(res.primary_emotion, 0) + 1
            
        return max(counts.items(), key=lambda x: x[1])[0]

    def reset_history(self):
        """Clear emotion history."""
        self._emotion_history.clear()
        logger.info("Emotion history cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get emotion engine statistics."""
        return {
            "history_size": len(self._emotion_history),
            "baseline_pitch": self._baseline_pitch,
            "baseline_intensity": self._baseline_intensity,
        }


# Global default emotion engine
default_voice_emotion: Optional[VoiceEmotionEngine] = None


def init_voice_emotion() -> VoiceEmotionEngine:
    """Initialize global voice emotion engine."""
    global default_voice_emotion
    default_voice_emotion = VoiceEmotionEngine()
    return default_voice_emotion
