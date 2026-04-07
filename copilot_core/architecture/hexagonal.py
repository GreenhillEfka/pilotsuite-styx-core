"""Hexagonal Architecture — Ports and Adapters for PilotSuite Core."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


# =============================================================================
# DOMAIN LAYER (Business Logic)
# =============================================================================

class Entity(ABC):
    """Base entity for domain objects."""
    
    @abstractmethod
    def get_id(self) -> str:
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass


class ValueObject(ABC):
    """Immutable value object."""
    
    @abstractmethod
    def equals(self, other: 'ValueObject') -> bool:
        pass


class AggregateRoot(Entity):
    """Aggregate root for consistency boundaries."""
    
    def __init__(self):
        self._events: List[Dict] = []
    
    def raise_event(self, event_type: str, payload: Dict):
        """Record domain event."""
        self._events.append({"type": event_type, "payload": payload})
    
    def get_events(self) -> List[Dict]:
        """Get uncommitted events."""
        events = self._events.copy()
        self._events.clear()
        return events


# =============================================================================
# PORT INTERFACES (Abstract Boundaries)
# =============================================================================

class InputPort(Protocol):
    """Primary/Driving port for incoming requests."""
    
    def execute(self, request: Any) -> Any:
        pass


class OutputPort(Protocol):
    """Secondary/Driven port for outgoing operations."""
    
    def save(self, entity: Entity) -> None:
        pass
    
    def find_by_id(self, entity_id: str) -> Optional[Entity]:
        pass


class Repository(Protocol):
    """Repository port for aggregate persistence."""
    
    def add(self, aggregate: AggregateRoot) -> None:
        pass
    
    def remove(self, aggregate: AggregateRoot) -> None:
        pass
    
    def find_by_id(self, id: str) -> Optional[AggregateRoot]:
        pass
    
    def find_all(self) -> List[AggregateRoot]:
        pass


# =============================================================================
# ADAPTER IMPLEMENTS (Concrete Implementations)
# =============================================================================

@dataclass
class AdapterConfig:
    """Adapter configuration."""
    name: str
    type: str
    config: Dict[str, Any]


class AdapterRegistry:
    """Registry for all adapters."""
    
    _instance: Optional['AdapterRegistry'] = None
    
    def __new__(cls) -> 'AdapterRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._adapters = {}
            cls._instance._ports = {}
        return cls._instance
    
    def register_adapter(self, name: str, adapter: Any, port: str):
        """Register adapter implementation for a port."""
        if port not in self._adapters:
            self._adapters[port] = {}
        self._adapters[port][name] = adapter
        logger.info(f"Adapter registered: {name} → {port}")
    
    def get_adapter(self, port: str, name: Optional[str] = None) -> Any:
        """Get adapter for port."""
        if port not in self._adapters:
            raise ValueError(f"No adapters for port: {port}")
        
        if name is None:
            # Return default (first) adapter
            return next(iter(self._adapters[port].values()))
        
        if name not in self._adapters[port]:
            raise ValueError(f"Adapter not found: {name} for port {port}")
        
        return self._adapters[port][name]
    
    def list_adapters(self, port: Optional[str] = None) -> Dict[str, List[str]]:
        """List all registered adapters."""
        if port:
            return {port: list(self._adapters.get(port, {}).keys())}
        return {port: list(adapters.keys()) for port, adapters in self._adapters.items()}


# =============================================================================
# CONCRETE ADAPTERS
# =============================================================================

class DatabaseAdapter:
    """Database adapter for repository port."""
    
    def __init__(self, connection_string: str):
        self._connection_string = connection_string
        self._connection = None
    
    async def connect(self):
        """Establish database connection."""
        logger.info(f"Connecting to database: {self._connection_string}")
        # Actual connection logic here
        self._connection = True
    
    async def disconnect(self):
        """Close database connection."""
        logger.info("Disconnecting from database")
        self._connection = None
    
    def save(self, entity: Entity) -> None:
        """Save entity to database."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        logger.debug(f"Saving entity: {entity.get_id()}")
        # Actual save logic here
    
    def find_by_id(self, entity_id: str) -> Optional[Entity]:
        """Find entity by ID."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        logger.debug(f"Finding entity: {entity_id}")
        # Actual find logic here
        return None


class RESTAdapter:
    """REST API adapter for input port."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self._host = host
        self._port = port
        self._routes: Dict[str, callable] = {}
    
    def register_route(self, path: str, handler: callable):
        """Register API route."""
        self._routes[path] = handler
        logger.info(f"REST route registered: {path}")
    
    async def start(self):
        """Start REST server."""
        logger.info(f"Starting REST server on {self._host}:{self._port}")
        # Actual server start logic here
    
    async def stop(self):
        """Stop REST server."""
        logger.info("Stopping REST server")


class WebSocketAdapter:
    """WebSocket adapter for real-time communication."""
    
    def __init__(self, path: str = "/ws"):
        self._path = path
        self._clients: set = set()
    
    async def connect(self, client):
        """Handle client connection."""
        self._clients.add(client)
        logger.info(f"WebSocket client connected: {client}")
    
    async def disconnect(self, client):
        """Handle client disconnection."""
        self._clients.discard(client)
        logger.info(f"WebSocket client disconnected: {client}")
    
    async def broadcast(self, message: Dict):
        """Broadcast message to all clients."""
        for client in self._clients.copy():
            try:
                await self._send(client, message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
    
    async def _send(self, client, message: Dict):
        """Send message to single client."""
        # Actual send logic here
        pass


class FileStorageAdapter:
    """File storage adapter for persistence."""
    
    def __init__(self, storage_path: str):
        self._storage_path = storage_path
    
    def save(self, key: str, data: Dict) -> None:
        """Save data to file."""
        import json
        from pathlib import Path
        
        path = Path(self._storage_path) / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.debug(f"Saved to file: {path}")
    
    def load(self, key: str) -> Optional[Dict]:
        """Load data from file."""
        import json
        from pathlib import Path
        
        path = Path(self._storage_path) / f"{key}.json"
        
        if not path.exists():
            return None
        
        with open(path, 'r') as f:
            return json.load(f)


# =============================================================================
# USE CASES (Application Business Rules)
# =============================================================================

class UseCase(ABC):
    """Base use case."""
    
    @abstractmethod
    def execute(self, request: Any) -> Any:
        pass


@dataclass
class CreateEntityRequest:
    """Request to create entity."""
    entity_type: str
    data: Dict[str, Any]


@dataclass
class GetEntityRequest:
    """Request to get entity."""
    entity_id: str


class CreateEntityUseCase(UseCase):
    """Use case for creating entities."""
    
    def __init__(self, repository: Repository):
        self._repository = repository
    
    def execute(self, request: CreateEntityRequest) -> Entity:
        """Execute use case."""
        # Business logic here
        logger.info(f"Creating entity: {request.entity_type}")
        # entity = EntityFactory.create(request.entity_type, request.data)
        # self._repository.add(entity)
        # return entity
        return None


class GetEntityUseCase(UseCase):
    """Use case for retrieving entities."""
    
    def __init__(self, repository: Repository):
        self._repository = repository
    
    def execute(self, request: GetEntityRequest) -> Optional[Entity]:
        """Execute use case."""
        logger.info(f"Getting entity: {request.entity_id}")
        return self._repository.find_by_id(request.entity_id)


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

class Container:
    """Dependency injection container."""
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
    
    def register(self, name: str, service: Any):
        """Register service."""
        self._services[name] = service
        logger.info(f"Service registered: {name}")
    
    def get(self, name: str) -> Any:
        """Get service."""
        if name not in self._services:
            raise ValueError(f"Service not found: {name}")
        return self._services[name]
    
    def has(self, name: str) -> bool:
        """Check if service exists."""
        return name in self._services


# Global default container
default_container: Optional[Container] = None


def init_hexagonal_architecture() -> Container:
    """Initialize hexagonal architecture with default adapters."""
    global default_container
    
    container = Container()
    
    # Register adapters
    registry = AdapterRegistry()
    registry.register_adapter("database", DatabaseAdapter("sqlite:///pilotsuite.db"), "Repository")
    registry.register_adapter("rest", RESTAdapter(), "InputPort")
    registry.register_adapter("websocket", WebSocketAdapter(), "InputPort")
    registry.register_adapter("file_storage", FileStorageAdapter("/config/storage"), "OutputPort")
    
    # Register services
    container.register("adapter_registry", registry)
    container.register("container", container)
    
    default_container = container
    logger.info("Hexagonal architecture initialized")
    
    return container
