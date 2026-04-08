"""Embedding Engine for Vector Store.

Generates embeddings for entities, preferences, and patterns using:
- Local feature-based embeddings (no external API required)
- Optional Ollama integration for semantic embeddings

The embedding model captures:
- Entity domain, area, capabilities
- User preference patterns
- Temporal patterns
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

# Embedding dimension (must match across all usages)
EMBEDDING_DIM = 128

# Feature dimensions for structured embeddings
DOMAIN_FEATURES = {
    "light": [1.0, 0.0, 0.0, 0.0, 0.0],
    "climate": [0.0, 1.0, 0.0, 0.0, 0.0],
    "media_player": [0.0, 0.0, 1.0, 0.0, 0.0],
    "sensor": [0.0, 0.0, 0.0, 1.0, 0.0],
    "switch": [0.0, 0.0, 0.0, 0.0, 1.0],
    "binary_sensor": [0.5, 0.0, 0.0, 0.5, 0.0],
    "cover": [0.0, 0.5, 0.0, 0.5, 0.0],
    "default": [0.2, 0.2, 0.2, 0.2, 0.2],
}

# Time-of-day buckets for temporal embeddings
TIME_BUCKETS = [
    (0, 6, "night"),      # 00:00 - 06:00
    (6, 12, "morning"),   # 06:00 - 12:00
    (12, 18, "afternoon"),# 12:00 - 18:00
    (18, 24, "evening"),  # 18:00 - 24:00
]


def _normalize(vec: list[float]) -> list[float]:
    """Normalize a vector to unit length."""
    magnitude = math.sqrt(sum(x * x for x in vec))
    if magnitude == 0:
        return vec
    return [x / magnitude for x in vec]


def _hash_to_vector(data: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Convert a string to a deterministic pseudo-random vector using hash."""
    result = []
    for i in range(dim):
        h = hashlib.md5(f"{data}:{i}".encode()).hexdigest()
        # Use first 8 hex chars as a float between -1 and 1
        val = int(h[:8], 16) / (16**8) * 2 - 1
        result.append(val)
    return _normalize(result)


@dataclass
class EmbeddingConfig:
    """Configuration for embedding engine."""
    
    dimension: int = EMBEDDING_DIM
    use_ollama: bool = False
    ollama_model: str = "nomic-embed-text"
    ollama_url: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    cache_embeddings: bool = True
    cache_max_size: int = 1000
    

@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    
    vector: list[float]
    dimension: int
    source: str  # "local" or "ollama"
    model: str
    cached: bool = False
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class EmbeddingEngine:
    """Engine for generating embeddings.
    
    Supports multiple strategies:
    1. Local feature-based embeddings (default, no external dependencies)
    2. Ollama embeddings (requires Ollama server with embedding model)
    
    Local embeddings are constructed from:
    - Entity domain (one-hot encoded)
    - Area/zone (hashed)
    - Capabilities (hashed)
    - Tags (hashed)
    - State patterns (temporal features)
    """
    
    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        """Initialize the embedding engine."""
        self.config = config or EmbeddingConfig()
        self._cache: dict[str, EmbeddingResult] = {}
        
    async def embed_entity(
        self,
        entity_id: str,
        domain: str | None = None,
        area: str | None = None,
        capabilities: list[str] | None = None,
        tags: list[str] | None = None,
        state: dict[str, Any] | None = None,
    ) -> EmbeddingResult:
        """Generate embedding for an entity.
        
        Args:
            entity_id: Home Assistant entity ID
            domain: Entity domain (light, climate, etc.)
            area: Area/zone the entity is in
            capabilities: List of entity capabilities
            tags: List of entity tags
            state: Current state dict (for dynamic features)
            
        Returns:
            EmbeddingResult with the embedding vector
        """
        # Build cache key
        cache_key = self._build_entity_cache_key(
            entity_id, domain, area, capabilities, tags
        )
        
        if self.config.cache_embeddings and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Generate embedding
        if self.config.use_ollama:
            result = await self._embed_ollama(cache_key)
        else:
            result = self._embed_entity_local(
                entity_id, domain, area, capabilities, tags, state
            )
        
        # Cache result
        if self.config.cache_embeddings:
            self._cache[cache_key] = result
            self._prune_cache()
            
        return result
    
    async def embed_user_preferences(
        self,
        user_id: str,
        preferences: dict[str, Any],
    ) -> EmbeddingResult:
        """Generate embedding for user preferences.
        
        Args:
            user_id: User identifier
            preferences: User preference dict (brightness, temperature, etc.)
            
        Returns:
            EmbeddingResult representing the user's preference profile
        """
        cache_key = f"user_pref:{user_id}:{hash(frozenset(str(preferences.items())))}"
        
        if self.config.cache_embeddings and cache_key in self._cache:
            return self._cache[cache_key]
        
        # Build preference embedding
        vec = [0.0] * self.config.dimension
        
        # Extract preference features
        idx = 0
        
        # Light brightness preference (normalized 0-1)
        light_pref = preferences.get("light_brightness", {})
        vec[idx] = light_pref.get("default", 0.5)
        idx += 1
        
        # Temperature preference (normalized: 15-30°C -> 0-1)
        temp_pref = preferences.get("temperature", {})
        temp = temp_pref.get("default", 21.0)
        vec[idx] = max(0, min(1, (temp - 15) / 15))
        idx += 1
        
        # Media volume preference
        media_pref = preferences.get("media_volume", {})
        vec[idx] = media_pref.get("default", 0.5)
        idx += 1
        
        # Mood weights
        mood = preferences.get("mood_weights", {})
        vec[idx] = mood.get("comfort", 0.5)
        idx += 1
        vec[idx] = mood.get("frugality", 0.5)
        idx += 1
        vec[idx] = mood.get("joy", 0.5)
        idx += 1
        
        # Hash user_id for personalization component
        user_vec = _hash_to_vector(f"user:{user_id}", self.config.dimension - idx)
        for i, val in enumerate(user_vec):
            if idx + i < self.config.dimension:
                vec[idx + i] = val
                
        result = EmbeddingResult(
            vector=_normalize(vec),
            dimension=self.config.dimension,
            source="local",
            model="preference_v1",
        )
        
        if self.config.cache_embeddings:
            self._cache[cache_key] = result
            self._prune_cache()
            
        return result
    
    async def embed_pattern(
        self,
        pattern_id: str,
        pattern_type: str,
        entities: list[str],
        conditions: dict[str, Any] | None = None,
        confidence: float = 0.0,
    ) -> EmbeddingResult:
        """Generate embedding for a pattern.
        
        Args:
            pattern_id: Pattern identifier
            pattern_type: Type of pattern (habitus, learned, manual)
            entities: List of entity IDs involved in pattern
            conditions: Pattern conditions (time, mood, etc.)
            confidence: Pattern confidence score
            
        Returns:
            EmbeddingResult representing the pattern
        """
        cache_key = f"pattern:{pattern_id}"
        
        if self.config.cache_embeddings and cache_key in self._cache:
            return self._cache[cache_key]
        
        vec = [0.0] * self.config.dimension
        idx = 0
        
        # Pattern type encoding
        type_encoding = {
            "habitus": [1.0, 0.0, 0.0],
            "learned": [0.0, 1.0, 0.0],
            "manual": [0.0, 0.0, 1.0],
        }.get(pattern_type, [0.33, 0.33, 0.33])
        for val in type_encoding:
            vec[idx] = val
            idx += 1
            
        # Confidence
        vec[idx] = confidence
        idx += 1
        
        # Entities (hash-based)
        entity_hash = _hash_to_vector(",".join(sorted(entities)), 32)
        for i, val in enumerate(entity_hash):
            if idx + i < self.config.dimension:
                vec[idx + i] = val
        idx += 32
        
        # Conditions (time, mood, etc.)
        if conditions:
            # Time bucket
            if "time_start" in conditions:
                hour = int(conditions["time_start"].split(":")[0])
                time_bucket = self._get_time_bucket(hour)
                time_encoding = {
                    "night": [1, 0, 0, 0],
                    "morning": [0, 1, 0, 0],
                    "afternoon": [0, 0, 1, 0],
                    "evening": [0, 0, 0, 1],
                }.get(time_bucket, [0.25, 0.25, 0.25, 0.25])
                for val in time_encoding:
                    if idx < self.config.dimension:
                        vec[idx] = val
                        idx += 1
                        
            # Mood encoding
            if "mood" in conditions:
                mood_hash = _hash_to_vector(f"mood:{conditions['mood']}", 16)
                for i, val in enumerate(mood_hash):
                    if idx + i < self.config.dimension:
                        vec[idx + i] = val
                idx += 16
                
        # Pattern ID hash for unique component
        id_hash = _hash_to_vector(f"pattern:{pattern_id}", self.config.dimension - idx)
        for i, val in enumerate(id_hash):
            if idx + i < self.config.dimension:
                vec[idx + i] = val
                
        result = EmbeddingResult(
            vector=_normalize(vec),
            dimension=self.config.dimension,
            source="local",
            model="pattern_v1",
        )
        
        if self.config.cache_embeddings:
            self._cache[cache_key] = result
            self._prune_cache()
            
        return result
    
    def _embed_entity_local(
        self,
        entity_id: str,
        domain: str | None,
        area: str | None,
        capabilities: list[str] | None,
        tags: list[str] | None,
        state: dict[str, Any] | None,
    ) -> EmbeddingResult:
        """Generate local feature-based embedding for an entity."""
        vec = [0.0] * self.config.dimension
        idx = 0
        
        # Extract domain from entity_id if not provided
        if not domain and "." in entity_id:
            domain = entity_id.split(".")[0]
            
        # Domain features (5 dims)
        domain_vec = DOMAIN_FEATURES.get(domain, DOMAIN_FEATURES["default"])
        for val in domain_vec:
            vec[idx] = val
            idx += 1
            
        # Entity ID hash (32 dims)
        entity_hash = _hash_to_vector(f"entity:{entity_id}", 32)
        for val in entity_hash:
            vec[idx] = val
            idx += 1
            
        # Area hash (16 dims)
        if area:
            area_hash = _hash_to_vector(f"area:{area}", 16)
            for val in area_hash:
                vec[idx] = val
                idx += 1
        else:
            idx += 16
            
        # Capabilities hash (32 dims)
        if capabilities:
            cap_hash = _hash_to_vector(f"caps:{','.join(sorted(capabilities))}", 32)
            for val in cap_hash:
                vec[idx] = val
                idx += 1
        else:
            idx += 32
            
        # Tags hash (32 dims)
        if tags:
            tags_hash = _hash_to_vector(f"tags:{','.join(sorted(tags))}", 32)
            for val in tags_hash:
                vec[idx] = val
                idx += 1
        else:
            idx += 32
            
        # State features (11 dims remaining)
        if state:
            # Numeric state (normalized)
            numeric_state = state.get("state")
            if isinstance(numeric_state, (int, float)):
                vec[idx] = max(0, min(1, float(numeric_state) / 100))
            idx += 1
            
            # Brightness (if present)
            brightness = state.get("attributes", {}).get("brightness")
            if brightness:
                vec[idx] = min(1, brightness / 255)
            idx += 1
            
            # Temperature (if present)
            temp = state.get("attributes", {}).get("temperature")
            if temp:
                vec[idx] = max(0, min(1, (temp - 15) / 15))
            idx += 1
            
            # Volume (if present)
            volume = state.get("attributes", {}).get("volume_level")
            if volume:
                vec[idx] = volume
            idx += 1
                
        return EmbeddingResult(
            vector=_normalize(vec),
            dimension=self.config.dimension,
            source="local",
            model="entity_v1",
        )
    
    async def _embed_ollama(self, text: str) -> EmbeddingResult:
        """Generate embedding using Ollama."""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.config.ollama_model,
                    "prompt": text,
                }
                async with session.post(
                    f"{self.config.ollama_url}/api/embeddings",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embedding = data.get("embedding", [])
                        return EmbeddingResult(
                            vector=_normalize(embedding[:self.config.dimension]),
                            dimension=self.config.dimension,
                            source="ollama",
                            model=self.config.ollama_model,
                        )
                    else:
                        _LOGGER.warning("Ollama embedding failed: %s", resp.status)
                        # Fallback to local
                        return self._embed_text_local(text)
        except Exception as e:
            _LOGGER.warning("Ollama embedding error: %s", e)
            return self._embed_text_local(text)
            
    def embed_text_sync(self, text: str) -> list[float]:
        """Generate embedding for arbitrary text (synchronous, bag-of-words).

        Hashes each word independently and averages the vectors.  Texts with
        similar vocabulary get similar embeddings — good enough for
        conversational RAG without requiring an external model.
        """
        import re as _re
        words = _re.findall(r"[a-zäöüß]+", text.lower())
        if not words:
            return [0.0] * self.config.dimension

        vec = [0.0] * self.config.dimension
        for word in words:
            word_vec = _hash_to_vector(f"word:{word}", self.config.dimension)
            for i in range(self.config.dimension):
                vec[i] += word_vec[i]

        n = len(words)
        vec = [v / n for v in vec]
        return _normalize(vec)

    def _embed_text_local(self, text: str) -> EmbeddingResult:
        """Generate local embedding for arbitrary text."""
        return EmbeddingResult(
            vector=_hash_to_vector(text, self.config.dimension),
            dimension=self.config.dimension,
            source="local",
            model="text_hash_v1",
        )
    
    def _build_entity_cache_key(
        self,
        entity_id: str,
        domain: str | None,
        area: str | None,
        capabilities: list[str] | None,
        tags: list[str] | None,
    ) -> str:
        """Build cache key for entity embedding."""
        parts = [f"entity:{entity_id}"]
        if domain:
            parts.append(f"d:{domain}")
        if area:
            parts.append(f"a:{area}")
        if capabilities:
            parts.append(f"c:{','.join(sorted(capabilities))}")
        if tags:
            parts.append(f"t:{','.join(sorted(tags))}")
        return ":".join(parts)
    
    def _get_time_bucket(self, hour: int) -> str:
        """Get time bucket for an hour."""
        for start, end, name in TIME_BUCKETS:
            if start <= hour < end:
                return name
        return "night"
    
    def _prune_cache(self) -> None:
        """Prune cache if it exceeds max size."""
        if len(self._cache) > self.config.cache_max_size:
            # Remove oldest half
            keys = list(self._cache.keys())
            for key in keys[:len(keys) // 2]:
                del self._cache[key]


# Singleton instance
_EMBEDDING_ENGINE: EmbeddingEngine | None = None


def get_embedding_engine(config: EmbeddingConfig | None = None) -> EmbeddingEngine:
    """Get the embedding engine singleton."""
    global _EMBEDDING_ENGINE
    if _EMBEDDING_ENGINE is None:
        # Build config from environment
        if config is None:
            config = EmbeddingConfig(
                use_ollama=os.environ.get("COPILOT_USE_OLLAMA", "").lower() == "true",
                ollama_model=os.environ.get("COPILOT_OLLAMA_MODEL", "nomic-embed-text"),
                ollama_url=os.environ.get("COPILOT_OLLAMA_URL", "http://localhost:11434"),
            )
        _EMBEDDING_ENGINE = EmbeddingEngine(config)
    return _EMBEDDING_ENGINE


def reset_embedding_engine() -> None:
    """Reset the embedding engine singleton (for testing)."""
    global _EMBEDDING_ENGINE
    _EMBEDDING_ENGINE = None