"""
CopilotModule Base Classes - PilotSuite v0.7.0 Modular Runtime Architecture

This module provides the foundational base classes for all Copilot Core modules,
ensuring consistent interface patterns, lifecycle management, and error handling.

Module Structure (9 Core Modules):
1. brain_graph  - Event processing and pattern detection
2. candidates  - Automation suggestion storage
3. habitus     - A→B pattern mining
4. mood        - Context-aware suggestion weighting
5. system_health - Zigbee/Z-Wave/Recorder monitoring
6. unifi       - Network monitoring
7. energy      - Energy monitoring and optimization
8. dev_surface - Development utilities
9. tags        - Tag System v0.2
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ModuleMetadata:
    """Metadata container for module information."""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str = "",
        author: str = "PilotSuite",
        dependencies: Optional[list[str]] = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.dependencies = dependencies or []
        self.loaded_at: Optional[datetime] = None
        self.load_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": self.dependencies,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "load_count": self.load_count,
        }


class CopilotModule(ABC):
    """
    Abstract base class for all PilotSuite modules.
    
    Provides:
    - Standardized module lifecycle (init, start, stop, shutdown)
    - Health check interface
    - Metrics collection
    - Error boundary handling
    - Configuration management
    
    Usage:
        class MyModule(CopilotModule):
            def __init__(self, config: Dict[str, Any] = None):
                super().__init__(
                    metadata=ModuleMetadata(
                        name="my_module",
                        version="1.0.0",
                        description="My custom module"
                    ),
                    config=config
                )
            
            async def _start_impl(self) -> None:
                # Initialization logic
                pass
            
            def health_check(self) -> Dict[str, Any]:
                return {"status": "healthy"}
    """
    
    def __init__(
        self,
        metadata: ModuleMetadata,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.metadata = metadata
        self.config = config or {}
        self._is_running = False
        self._is_initialized = False
        self._startup_error: Optional[str] = None
        self._metrics: Dict[str, Any] = {}
        
        logger.info(f"Module '{metadata.name}' initialized (v{metadata.version})")
    
    @property
    def name(self) -> str:
        """Module name alias for convenience."""
        return self.metadata.name
    
    @property
    def version(self) -> str:
        """Module version alias for convenience."""
        return self.metadata.version
    
    @property
    def is_running(self) -> bool:
        """Check if module is currently running."""
        return self._is_running
    
    @property
    def is_initialized(self) -> bool:
        """Check if module has been initialized."""
        return self._is_initialized
    
    @property
    def startup_error(self) -> Optional[str]:
        """Get any error that occurred during startup."""
        return self._startup_error
    
    def initialize(self) -> bool:
        """
        Initialize the module. Called once before start().
        
        Returns:
            True if initialization succeeded, False otherwise.
        """
        try:
            self.metadata.load_count += 1
            self.metadata.loaded_at = datetime.utcnow()
            result = self._init_impl()
            self._is_initialized = result
            if result:
                logger.info(f"Module '{self.name}' initialization complete")
            else:
                self._startup_error = "Initialization returned False"
                logger.error(f"Module '{self.name}' initialization failed")
            return result
        except Exception as e:
            self._startup_error = str(e)
            logger.exception(f"Module '{self.name}' initialization error: {e}")
            return False
    
    def start(self) -> bool:
        """
        Start the module. Called after initialize().
        
        Returns:
            True if startup succeeded, False otherwise.
        """
        if not self._is_initialized:
            self._startup_error = "Module not initialized"
            logger.error(f"Module '{self.name}' cannot start: not initialized")
            return False
        
        try:
            result = self._start_impl()
            self._is_running = result
            if result:
                logger.info(f"Module '{self.name}' started")
            else:
                self._startup_error = "Startup returned False"
                logger.error(f"Module '{self.name}' startup failed")
            return result
        except Exception as e:
            self._startup_error = str(e)
            logger.exception(f"Module '{self.name}' startup error: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the module gracefully.
        
        Returns:
            True if stop succeeded, False otherwise.
        """
        try:
            result = self._stop_impl()
            self._is_running = False
            logger.info(f"Module '{self.name}' stopped")
            return result if result is not None else True
        except Exception as e:
            logger.exception(f"Module '{self.name}' stop error: {e}")
            return False
    
    def shutdown(self) -> None:
        """
        Irreversible shutdown. Release all resources.
        """
        try:
            self._shutdown_impl()
            logger.info(f"Module '{self.name}' shutdown complete")
        except Exception as e:
            logger.exception(f"Module '{self.name}' shutdown error: {e}")
    
    # === Abstract Methods ===
    
    @abstractmethod
    def _init_impl(self) -> bool:
        """Implementation-specific initialization logic."""
        pass
    
    @abstractmethod
    def _start_impl(self) -> bool:
        """Implementation-specific startup logic."""
        pass
    
    def _stop_impl(self) -> bool:
        """Implementation-specific stop logic. Override if needed."""
        return True
    
    def _shutdown_impl(self) -> None:
        """Implementation-specific shutdown logic. Override if needed."""
        pass
    
    # === Health & Metrics ===
    
    def health_check(self) -> Dict[str, Any]:
        """
        Module health check. Override in subclasses for specific checks.
        
        Returns:
            Dict containing health status and relevant metrics.
        """
        return {
            "status": "healthy" if self._is_running else "stopped",
            "name": self.name,
            "version": self.version,
            "initialized": self._is_initialized,
            "running": self._is_running,
            "metrics": self._metrics,
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get module-specific metrics."""
        return self._metrics.copy()
    
    def record_metric(self, key: str, value: Any) -> None:
        """Record a metric value."""
        self._metrics[key] = value
    
    def increment_metric(self, key: str, amount: int = 1) -> None:
        """Increment a numeric metric."""
        self._metrics[key] = self._metrics.get(key, 0) + amount
    
    def get_info(self) -> Dict[str, Any]:
        """Get comprehensive module information."""
        return {
            "metadata": self.metadata.to_dict(),
            "state": {
                "initialized": self._is_initialized,
                "running": self._is_running,
                "startup_error": self._startup_error,
            },
            "metrics": self._metrics,
            "health": self.health_check(),
        }


class CopilotService(CopilotModule):
    """
    Base class for service-type modules that handle background operations.
    
    Extends CopilotModule with:
    - Background task management
    - Interval-based execution
    - State persistence interface
    """
    
    def __init__(
        self,
        metadata: ModuleMetadata,
        config: Optional[Dict[str, Any]] = None,
        persistent_state_path: Optional[str] = None,
    ):
        super().__init__(metadata=metadata, config=config)
        self._state: Dict[str, Any] = {}
        self._state_path = persistent_state_path
        self._tasks: list = []
    
    # === State Management ===
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self._state.get(key, default)
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a state value."""
        self._state[key] = value
    
    def load_state(self) -> bool:
        """Load state from persistent storage."""
        if not self._state_path:
            return False
        try:
            import json
            from pathlib import Path
            path = Path(self._state_path)
            if path.exists():
                with open(path, 'r') as f:
                    self._state = json.load(f)
                logger.info(f"Module '{self.name}' loaded state from {self._state_path}")
                return True
        except Exception as e:
            logger.error(f"Module '{self.name}' state load error: {e}")
        return False
    
    def save_state(self) -> bool:
        """Save state to persistent storage."""
        if not self._state_path:
            return False
        try:
            import json
            from pathlib import Path
            path = Path(self._state_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self._state, f)
            return True
        except Exception as e:
            logger.error(f"Module '{self.name}' state save error: {e}")
        return False
    
    # === Health Override ===
    
    def health_check(self) -> Dict[str, Any]:
        """Extended health check including state info."""
        base_health = super().health_check()
        return {
            **base_health,
            "state_keys": list(self._state.keys()),
            "active_tasks": len(self._tasks),
        }


class CopilotAPI(CopilotModule):
    """
    Base class for API/Blueprint-type modules.
    
    Extends CopilotModule with:
    - Flask blueprint support
    - Route registration
    - Request/response utilities
    """
    
    def __init__(
        self,
        metadata: ModuleMetadata,
        config: Optional[Dict[str, Any]] = None,
        blueprint_url_prefix: str = "/api/v1",
    ):
        super().__init__(metadata=metadata, config=config)
        self._blueprint_url_prefix = blueprint_url_prefix
        self._blueprint = None
    
    @property
    def blueprint_url_prefix(self) -> str:
        """Get the URL prefix for this API's blueprint."""
        return self._blueprint_url_prefix
    
    def get_blueprint(self):
        """Get or create the Flask blueprint for this API."""
        if self._blueprint is None:
            from flask import Blueprint
            self._blueprint = Blueprint(
                self.name,
                __name__,
                url_prefix=self._blueprint_url_prefix
            )
            self._register_routes()
        return self._blueprint
    
    @abstractmethod
    def _register_routes(self) -> None:
        """Register Flask routes. Override in subclasses."""
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """Extended health check including API info."""
        base_health = super().health_check()
        return {
            **base_health,
            "blueprint_url_prefix": self._blueprint_url_prefix,
            "blueprint_registered": self._blueprint is not None,
        }


# === Module Registry ===

class ModuleRegistry:
    """
    Registry for managing Copilot module lifecycle.
    
    Provides:
    - Module registration and discovery
    - Dependency resolution
    - Bulk lifecycle operations
    """
    
    _instance: Optional["ModuleRegistry"] = None
    _modules: Dict[str, CopilotModule] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, module: CopilotModule) -> bool:
        """Register a module."""
        if module.name in self._modules:
            logger.warning(f"Module '{module.name}' already registered, overwriting")
        self._modules[module.name] = module
        logger.info(f"Registered module: {module.name} v{module.version}")
        return True
    
    def get(self, name: str) -> Optional[CopilotModule]:
        """Get a registered module by name."""
        return self._modules.get(name)
    
    def list_modules(self) -> list[str]:
        """List all registered module names."""
        return list(self._modules.keys())
    
    def initialize_all(self) -> Dict[str, bool]:
        """Initialize all registered modules."""
        results = {}
        for name, module in self._modules.items():
            results[name] = module.initialize()
        return results
    
    def start_all(self) -> Dict[str, bool]:
        """Start all registered modules."""
        results = {}
        for name, module in self._modules.items():
            results[name] = module.start()
        return results
    
    def stop_all(self) -> Dict[str, bool]:
        """Stop all registered modules."""
        results = {}
        for name, module in self._modules.items():
            results[name] = module.stop()
        return results
    
    def shutdown_all(self) -> None:
        """Shutdown all modules."""
        for module in self._modules.values():
            module.shutdown()
        self._modules.clear()
        logger.info("All modules shut down")
    
    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Run health check on all modules."""
        return {name: module.health_check() for name, module in self._modules.items()}


# === Convenience Functions ===

def create_module_metadata(
    name: str,
    version: str,
    description: str = "",
    author: str = "PilotSuite",
    dependencies: Optional[list[str]] = None,
) -> ModuleMetadata:
    """Factory function for creating ModuleMetadata."""
    return ModuleMetadata(
        name=name,
        version=version,
        description=description,
        author=author,
        dependencies=dependencies,
    )


def get_registry() -> ModuleRegistry:
    """Get the global module registry instance."""
    return ModuleRegistry()
