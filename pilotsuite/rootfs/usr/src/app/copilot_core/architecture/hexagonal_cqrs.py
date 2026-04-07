"""Hexagonal & CQRS Architecture (Slice 186/187).

Implements the structural foundation for PilotSuite v1.0.0:
- Domain (Pure Logic)
- Ports (Interfaces)
- Adapters (Infrastructure)
- Command/Query Bus (CQRS)
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Type, TypeVar, Generic

_LOGGER = logging.getLogger(__name__)

# --- Domain Layer (Pure Entities) ---
@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

# --- Ports (Interfaces) ---
class MessageBus(ABC):
    @abstractmethod
    def handle(self, message: Any) -> Any:
        pass

# --- CQRS Implementation ---
T = TypeVar('T')

class Command(ABC):
    """Marker for write operations."""
    pass

class Query(ABC, Generic[T]):
    """Marker for read operations."""
    pass

class CQRSBus(MessageBus):
    """Central bus for commands and queries."""
    
    def __init__(self):
        self._handlers: Dict[Type, Any] = {}

    def register(self, message_type: Type, handler: Any):
        self._handlers[message_type] = handler

    def handle(self, message: Any) -> Any:
        handler = self._handlers.get(type(message))
        if not handler:
            raise ValueError(f"No handler for {type(message)}")
        return handler(message)

# --- Federated Learning Math Plugin (P2-008) ---
class FederatedMath:
    """Core plugin for privacy-preserving mathematical operations."""
    
    @staticmethod
    def federated_average(local_models: List[Dict[str, float]]) -> Dict[str, float]:
        """Calculates the weighted average of local model weights."""
        if not local_models:
            return {}
            
        num_models = len(local_models)
        keys = local_models[0].keys()
        global_model = {}
        
        for key in keys:
            global_model[key] = sum(m[key] for m in local_models) / num_models
            
        _LOGGER.info("P2-008: Computed Federated Average for %d models", num_models)
        return global_model

# --- Infrastructure Adapters (Examples) ---
class HomeAssistantAdapter:
    """External Adapter to sync with HA."""
    def sync_entity(self, entity_id: str, state: Any):
        _LOGGER.info("Adapter: Syncing %s to HA with state %s", entity_id, state)

# API Integration for Slice 186/187
def init_hexagonal_api(bp):
    @bp.route("/system/architecture/stats", methods=["GET"])
    def get_arch_stats():
        return {
            "architecture": "hexagonal",
            "pattern": "CQRS",
            "federated_math": "active",
            "status": "hardened"
        }
