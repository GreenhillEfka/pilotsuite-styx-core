"""Multi-Speaker Tracking — Voice ID, Speaker Identification, Diarization."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import time
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class SpeakerProfile:
    """Voice profile for a speaker."""
    id: str
    name: str
    embedding: List[float]
    created_at: float = field(default_factory=lambda: time.time())
    last_seen: Optional[float] = None
    voice_print_hash: str = ""


@dataclass
class SpeakerIdentification:
    """Identification result."""
    speaker_id: str
    confidence: float
    is_known: bool
    segment_id: str


class MultiSpeakerTracker:
    """Identifies and tracks multiple speakers in voice interactions."""

    def __init__(self):
        self._profiles: Dict[str, SpeakerProfile] = {}
        self._identification_history: List[SpeakerIdentification] = []
        self._embedding_dim = 128

    def identify_speaker(self, audio_data: Any) -> SpeakerIdentification:
        """Identify speaker from audio segment."""
        logger.info("Identifying speaker...")
        
        # Simulated embedding extraction
        # In production, would use SpeakerNet/ResNet
        current_embedding = self._extract_embedding(audio_data)
        
        best_id = "unknown"
        max_similarity = 0.0
        
        for profile in self._profiles.values():
            similarity = self._cosine_similarity(current_embedding, profile.embedding)
            if similarity > max_similarity:
                max_similarity = similarity
                best_id = profile.id
                
        # Threshold for known speaker
        is_known = max_similarity > 0.85
        
        result = SpeakerIdentification(
            speaker_id=best_id if is_known else "unknown",
            confidence=max_similarity if is_known else 1.0 - max_similarity,
            is_known=is_known,
            segment_id=f"seg_{int(time.time())}"
        )
        
        if is_known:
            self._profiles[best_id].last_seen = time.time()
            
        self._identification_history.append(result)
        logger.info(f"Speaker identified: {result.speaker_id} (conf: {result.confidence:.2f})")
        
        return result

    def enroll_speaker(self, name: str, audio_data: Any) -> str:
        """Enroll a new speaker profile."""
        embedding = self._extract_embedding(audio_data)
        speaker_id = hashlib.sha256(name.encode()).hexdigest()[:8]
        
        profile = SpeakerProfile(
            id=speaker_id,
            name=name,
            embedding=embedding,
            voice_print_hash=hashlib.md5(str(embedding).encode()).hexdigest()
        )
        
        self._profiles[speaker_id] = profile
        logger.info(f"Speaker enrolled: {name} ({speaker_id})")
        return speaker_id

    def _extract_embedding(self, audio_data: Any) -> List[float]:
        """Extract voice embedding vector."""
        # Simulated extraction
        return [0.1] * self._embedding_dim

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Calculate cosine similarity."""
        return 0.9  # Simulated match

    def get_stats(self) -> Dict[str, Any]:
        """Get speaker tracker statistics."""
        return {
            "enrolled_speakers": len(self._profiles),
            "history_size": len(self._identification_history),
            "last_speaker": self._identification_history[-1].speaker_id if self._identification_history else None,
        }


# Global default speaker tracker
default_speaker_tracker: Optional[MultiSpeakerTracker] = None


def init_speaker_tracker() -> MultiSpeakerTracker:
    """Initialize global speaker tracker."""
    global default_speaker_tracker
    default_speaker_tracker = MultiSpeakerTracker()
    return default_speaker_tracker
