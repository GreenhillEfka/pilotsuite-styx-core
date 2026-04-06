"""Rule Cache — Symbiosis Layer.
Caches rule evaluation results to reduce latency.
"""
import hashlib
import json
import logging
from typing import List, Dict, Optional
from ..cache import get_habitus_cache

_LOGGER = logging.getLogger(__name__)

class RuleCache:
    def __init__(self, cache_manager=None):
        self.cache = cache_manager or get_habitus_cache()
        self.ttl = 60  # Cache for 60 seconds as per requirement

    def _generate_key(self, zone_id: str, current_events: List[dict]) -> str:
        """Generates a unique and stable cache key for rule evaluation."""
        # Ensure events are deterministic for key generation
        events_str = json.dumps(current_events, sort_keys=True)
        key_content = f"rule_eval:{zone_id}:{events_str}"
        return f"rule_eval:{hashlib.md5(key_content.encode()).hexdigest()}"

    async def get_evaluation(self, zone_id: str, current_events: List[dict]) -> Optional[List[dict]]:
        """Retrieve cached rule evaluation results."""
        key = self._generate_key(zone_id, current_events)
        result = await self.cache.get(key)
        if result is not None:
            _LOGGER.debug(f"Cache hit for zone evaluation: {zone_id}")
        return result

    async def set_evaluation(self, zone_id: str, current_events: List[dict], result: List[dict]):
        """Cache rule evaluation results."""
        key = self._generate_key(zone_id, current_events)
        await self.cache.set(key, result, ttl=self.ttl)
        _LOGGER.debug(f"Cached result for zone evaluation: {zone_id}")

_rule_cache = None

def get_rule_cache():
    global _rule_cache
    if _rule_cache is None:
        _rule_cache = RuleCache()
    return _rule_cache
