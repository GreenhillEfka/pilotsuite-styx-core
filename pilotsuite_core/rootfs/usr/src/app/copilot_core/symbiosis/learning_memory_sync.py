"""Learning Memory Sync — Runtime Symbiosis Layer.
Bridges HA learned patterns to Core Learning Memory.
"""
from __future__ import annotations
import logging, requests
from typing import Dict, List
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

@dataclass
class LearnedPattern:
    pattern_id: str
    context: dict
    frequency: int
    confidence: float

class LearningMemorySync:
    """Syncs learned patterns to Core."""
    
    def __init__(self, core_url: str, ha_url: str, ha_token: str):
        self.core_url = core_url
        self.ha_url = ha_url
        self.ha_token = ha_token
    
    async def store_pattern(self, pattern: LearnedPattern) -> bool:
        payload = {
            "pattern_id": pattern.pattern_id,
            "context": pattern.context,
            "frequency": pattern.frequency,
            "confidence": pattern.confidence
        }
        try:
            resp = requests.post(f"{self.core_url}/api/v1/memory/patterns/store", json=payload, timeout=5)
            return resp.status_code in (200, 201)
        except Exception as e:
            _LOGGER.error(f"Pattern store failed: {e}")
            return False
