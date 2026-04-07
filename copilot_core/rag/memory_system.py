"""P2-005: Memory System — Episodic, Semantic, Procedural Memory."""
from __future__ import annotations

import logging
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memory."""
    EPISODIC = "episodic"  # Events and experiences
    SEMANTIC = "semantic"  # Facts and knowledge
    PROCEDURAL = "procedural"  # Skills and procedures


@dataclass
class Memory:
    """Single memory entry."""
    id: str
    type: MemoryType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 1.0


@dataclass
class MemoryQuery:
    """Query for memory retrieval."""
    text: str
    memory_type: Optional[MemoryType] = None
    time_range: Optional[tuple] = None
    max_results: int = 10


class MemorySystem:
    """Long-term memory system with multiple memory types."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._memories: Dict[str, Memory] = {}
        self._episodic: List[str] = []
        self._semantic: Dict[str, str] = {}
        self._procedural: Dict[str, str] = {}
        
        self._load_memories()

    def add_memory(
        self,
        content: str,
        memory_type: MemoryType,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 1.0,
    ) -> str:
        """Add a new memory."""
        import hashlib
        memory_id = hashlib.sha256(f"{content}{time.time()}".encode()).hexdigest()[:16]
        
        memory = Memory(
            id=memory_id,
            type=memory_type,
            content=content,
            metadata=metadata or {},
            importance=importance
        )
        
        self._memories[memory_id] = memory
        
        # Index by type
        if memory_type == MemoryType.EPISODIC:
            self._episodic.append(memory_id)
        elif memory_type == MemoryType.SEMANTIC:
            key = metadata.get("key", content[:50]) if metadata else content[:50]
            self._semantic[key] = memory_id
        elif memory_type == MemoryType.PROCEDURAL:
            key = metadata.get("skill", content[:50]) if metadata else content[:50]
            self._procedural[key] = memory_id
        
        self._save_memories()
        logger.debug(f"Added {memory_type.value} memory: {memory_id}")
        
        return memory_id

    def query_memories(self, query: MemoryQuery) -> List[Memory]:
        """Query memories."""
        results = []
        
        for memory_id, memory in self._memories.items():
            # Filter by type
            if query.memory_type and memory.type != query.memory_type:
                continue
            
            # Filter by time range
            if query.time_range:
                start, end = query.time_range
                if not (start <= memory.created_at <= end):
                    continue
            
            # Simple text match (would use embeddings in production)
            if query.text.lower() in memory.content.lower():
                results.append(memory)
            
            if len(results) >= query.max_results:
                break
        
        # Update access stats
        for memory in results:
            memory.accessed_at = time.time()
            memory.access_count += 1
        
        return results

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get single memory by ID."""
        memory = self._memories.get(memory_id)
        if memory:
            memory.accessed_at = time.time()
            memory.access_count += 1
        return memory

    def delete_memory(self, memory_id: str) -> bool:
        """Delete memory."""
        if memory_id not in self._memories:
            return False
        
        memory = self._memories[memory_id]
        
        # Remove from index
        if memory.type == MemoryType.EPISODIC:
            if memory_id in self._episodic:
                self._episodic.remove(memory_id)
        elif memory.type == MemoryType.SEMANTIC:
            self._semantic = {k: v for k, v in self._semantic.items() if v != memory_id}
        elif memory.type == MemoryType.PROCEDURAL:
            self._procedural = {k: v for k, v in self._procedural.items() if v != memory_id}
        
        del self._memories[memory_id]
        self._save_memories()
        
        return True

    def consolidate_memories(self) -> Dict[str, Any]:
        """Consolidate memories (nightly distillation)."""
        # Remove low-importance, rarely accessed memories
        to_remove = []
        for memory_id, memory in self._memories.items():
            age_days = (time.time() - memory.created_at) / (24 * 3600)
            if memory.importance < 0.3 and memory.access_count == 0 and age_days > 7:
                to_remove.append(memory_id)
        
        for memory_id in to_remove:
            self.delete_memory(memory_id)
        
        stats = {
            "total_memories": len(self._memories),
            "episodic": len(self._episodic),
            "semantic": len(self._semantic),
            "procedural": len(self._procedural),
            "removed": len(to_remove),
        }
        
        logger.info(f"Memory consolidation: {stats}")
        return stats

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        total_access = sum(m.access_count for m in self._memories.values())
        avg_importance = sum(m.importance for m in self._memories.values()) / max(1, len(self._memories))
        
        return {
            "total_memories": len(self._memories),
            "episodic": len(self._episodic),
            "semantic": len(self._semantic),
            "procedural": len(self._procedural),
            "total_accesses": total_access,
            "avg_importance": avg_importance,
        }

    def _save_memories(self):
        """Save memories to disk."""
        memories_file = self.data_dir / "memories.json"
        
        data = {}
        for memory_id, memory in self._memories.items():
            data[memory_id] = {
                "id": memory.id,
                "type": memory.type.value,
                "content": memory.content,
                "metadata": memory.metadata,
                "created_at": memory.created_at,
                "accessed_at": memory.accessed_at,
                "access_count": memory.access_count,
                "importance": memory.importance,
            }
        
        with open(memories_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _load_memories(self):
        """Load memories from disk."""
        memories_file = self.data_dir / "memories.json"
        
        if not memories_file.exists():
            logger.info("No existing memories found")
            return
        
        try:
            with open(memories_file, 'r') as f:
                data = json.load(f)
            
            for memory_id, memory_data in data.items():
                memory = Memory(
                    id=memory_data["id"],
                    type=MemoryType(memory_data["type"]),
                    content=memory_data["content"],
                    metadata=memory_data.get("metadata", {}),
                    created_at=memory_data.get("created_at", 0),
                    accessed_at=memory_data.get("accessed_at", 0),
                    access_count=memory_data.get("access_count", 0),
                    importance=memory_data.get("importance", 1.0),
                )
                self._memories[memory_id] = memory
                
                # Rebuild indexes
                if memory.type == MemoryType.EPISODIC:
                    self._episodic.append(memory_id)
                elif memory.type == MemoryType.SEMANTIC:
                    key = memory.metadata.get("key", memory.content[:50])
                    self._semantic[key] = memory_id
                elif memory.type == MemoryType.PROCEDURAL:
                    key = memory.metadata.get("skill", memory.content[:50])
                    self._procedural[key] = memory_id
            
            logger.info(f"Loaded {len(self._memories)} memories")
        except Exception as e:
            logger.error(f"Failed to load memories: {e}")


# Global default memory system
default_memory_system: Optional[MemorySystem] = None


def init_memory_system(data_dir: str) -> MemorySystem:
    """Initialize global memory system."""
    global default_memory_system
    default_memory_system = MemorySystem(data_dir)
    return default_memory_system


def add_memory(content: str, memory_type: MemoryType, **kwargs) -> str:
    """Convenience function to add memory."""
    if default_memory_system:
        return default_memory_system.add_memory(content, memory_type, **kwargs)
    return ""


def query_memories(query: str, **kwargs) -> List[Memory]:
    """Convenience function to query memories."""
    if default_memory_system:
        q = MemoryQuery(text=query, **kwargs)
        return default_memory_system.query_memories(q)
    return []
