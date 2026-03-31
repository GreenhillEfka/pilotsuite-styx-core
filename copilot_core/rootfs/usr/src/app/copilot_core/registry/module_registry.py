"""Module Registry — Slice 79.

Lightweight Module Discovery und Registration.

Features:
- Module Discovery (auto-detect available modules)
- Module Registration (explicit registration)
- Capability Advertisement (what can this module do?)
- Module Health Status
- Module Metadata (version, author, description)
- Module Dependencies (inter-module requirements)
- Module Tags (search/filter)

NO Config Management — modules are autonomous.
This is ONLY for discovery and metadata.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ModuleType(Enum):
    """Module types."""
    SENSOR = "sensor"  # Input modules (presence, light level, etc.)
    ACTUATOR = "actuator"  # Output modules (light, hvac, etc.)
    LOGIC = "logic"  # Processing modules (rules, orchestration)
    UTILITY = "utility"  # Helper modules (time of day, config, etc.)
    INTEGRATION = "integration"  # External integrations (HA, MQTT, etc.)


class ModuleHealth(Enum):
    """Module health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ModuleCapability:
    """Module capability advertisement."""
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "parameters": self.parameters,
        }


@dataclass
class ModuleDependency:
    """Module dependency declaration."""
    module_id: str
    required: bool = True
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "required": self.required,
            "min_version": self.min_version,
            "max_version": self.max_version,
        }


@dataclass
class ModuleMetadata:
    """Module metadata."""
    module_id: str
    name: str
    version: str
    module_type: ModuleType
    description: str = ""
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    tags: List[str] = field(default_factory=list)
    capabilities: List[ModuleCapability] = field(default_factory=list)
    dependencies: List[ModuleDependency] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "name": self.name,
            "version": self.version,
            "module_type": self.module_type.value,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "tags": self.tags,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ModuleHealthStatus:
    """Module health status."""
    module_id: str
    health: ModuleHealth
    last_check: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None
    uptime_seconds: float = 0.0
    last_error: Optional[str] = None
    error_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "health": self.health.value,
            "last_check": self.last_check,
            "error_message": self.error_message,
            "uptime_seconds": self.uptime_seconds,
            "last_error": self.last_error,
            "error_count": self.error_count,
        }


@dataclass
class ModuleRegistration:
    """Registered module instance."""
    metadata: ModuleMetadata
    instance: Any  # The actual module instance
    health: ModuleHealthStatus
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "health": self.health.to_dict(),
            "registered_at": self.registered_at,
            "enabled": self.enabled,
        }


class ModuleRegistry:
    """Lightweight module registry for discovery.
    
    Principles:
    - NO config management (modules are autonomous)
    - ONLY discovery and metadata
    - Health monitoring
    - Capability advertisement
    
    Usage:
        registry = ModuleRegistry()
        registry.register(module_metadata, module_instance)
        modules = registry.find_by_capability("presence_detection")
        health = registry.get_health("presence_module")
    """
    
    def __init__(self):
        self._modules: Dict[str, ModuleRegistration] = {}
        self._health_checks: Dict[str, Callable] = {}  # module_id -> health check function
        self._start_times: Dict[str, datetime] = {}
        
        logger.info("ModuleRegistry initialized")
    
    def register(self, metadata: ModuleMetadata, instance: Any,
                health_check: Optional[Callable] = None) -> bool:
        """Register a module."""
        if metadata.module_id in self._modules:
            logger.warning("Module already registered: %s", metadata.module_id)
            return False
        
        health = ModuleHealthStatus(
            module_id=metadata.module_id,
            health=ModuleHealth.UNKNOWN,
        )
        
        registration = ModuleRegistration(
            metadata=metadata,
            instance=instance,
            health=health,
        )
        
        with self._lock():
            self._modules[metadata.module_id] = registration
            self._start_times[metadata.module_id] = datetime.now(timezone.utc)
            
            if health_check:
                self._health_checks[metadata.module_id] = health_check
        
        # Initial health check
        self.check_health(metadata.module_id)
        
        logger.info("Module registered: %s v%s", metadata.name, metadata.version)
        return True
    
    def unregister(self, module_id: str) -> bool:
        """Unregister a module."""
        if module_id not in self._modules:
            return False
        
        with self._lock():
            del self._modules[module_id]
            
            if module_id in self._start_times:
                del self._start_times[module_id]
            
            if module_id in self._health_checks:
                del self._health_checks[module_id]
        
        logger.info("Module unregistered: %s", module_id)
        return True
    
    def get_module(self, module_id: str) -> Optional[Any]:
        """Get module instance by ID."""
        registration = self._modules.get(module_id)
        
        if not registration:
            return None
        
        return registration.instance
    
    def get_metadata(self, module_id: str) -> Optional[ModuleMetadata]:
        """Get module metadata."""
        registration = self._modules.get(module_id)
        
        if not registration:
            return None
        
        return registration.metadata
    
    def get_health(self, module_id: str) -> Optional[ModuleHealthStatus]:
        """Get module health status."""
        registration = self._modules.get(module_id)
        
        if not registration:
            return None
        
        return registration.health
    
    def check_health(self, module_id: str) -> ModuleHealth:
        """Check module health."""
        if module_id not in self._modules:
            return ModuleHealth.UNKNOWN
        
        registration = self._modules[module_id]
        health_check = self._health_checks.get(module_id)
        
        if health_check:
            try:
                result = health_check(registration.instance)
                
                if result:
                    registration.health.health = ModuleHealth.HEALTHY
                    registration.health.error_message = None
                else:
                    registration.health.health = ModuleHealth.DEGRADED
                    registration.health.error_message = "Health check failed"
                    
            except Exception as e:
                registration.health.health = ModuleHealth.UNHEALTHY
                registration.health.error_message = str(e)
                registration.health.error_count += 1
                registration.health.last_error = str(e)
        else:
            # No health check = assume healthy if registered
            registration.health.health = ModuleHealth.HEALTHY
        
        registration.health.last_check = datetime.now(timezone.utc).isoformat()
        
        # Update uptime
        if module_id in self._start_times:
            start = self._start_times[module_id]
            registration.health.uptime_seconds = (
                datetime.now(timezone.utc) - start
            ).total_seconds()
        
        return registration.health.health
    
    def check_all_health(self) -> Dict[str, ModuleHealth]:
        """Check health of all modules."""
        results = {}
        
        for module_id in self._modules:
            results[module_id] = self.check_health(module_id)
        
        return results
    
    def find_by_capability(self, capability_name: str) -> List[str]:
        """Find modules that provide a capability."""
        matching = []
        
        for module_id, registration in self._modules.items():
            for cap in registration.metadata.capabilities:
                if cap.name == capability_name:
                    matching.append(module_id)
                    break
        
        return matching
    
    def find_by_type(self, module_type: ModuleType) -> List[str]:
        """Find modules by type."""
        return [
            module_id for module_id, reg in self._modules.items()
            if reg.metadata.module_type == module_type
        ]
    
    def find_by_tag(self, tag: str) -> List[str]:
        """Find modules by tag."""
        return [
            module_id for module_id, reg in self._modules.items()
            if tag in reg.metadata.tags
        ]
    
    def find_by_tags(self, tags: List[str], match_all: bool = False) -> List[str]:
        """Find modules by multiple tags."""
        results = []
        
        for module_id, reg in self._modules.items():
            module_tags = set(reg.metadata.tags)
            
            if match_all:
                if all(t in module_tags for t in tags):
                    results.append(module_id)
            else:
                if any(t in module_tags for t in tags):
                    results.append(module_id)
        
        return results
    
    def list_modules(self, enabled_only: bool = False) -> List[str]:
        """List all registered module IDs."""
        if enabled_only:
            return [
                m for m, reg in self._modules.items()
                if reg.enabled
            ]
        return list(self._modules.keys())
    
    def enable_module(self, module_id: str) -> bool:
        """Enable a module."""
        if module_id not in self._modules:
            return False
        
        self._modules[module_id].enabled = True
        return True
    
    def disable_module(self, module_id: str) -> bool:
        """Disable a module."""
        if module_id not in self._modules:
            return False
        
        self._modules[module_id].enabled = False
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        by_type = {}
        by_health = {}
        
        for reg in self._modules.values():
            # By type
            type_name = reg.metadata.module_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
            
            # By health
            health_name = reg.health.health.value
            by_health[health_name] = by_health.get(health_name, 0) + 1
        
        return {
            "total_modules": len(self._modules),
            "enabled_modules": len([m for m, reg in self._modules.items() if reg.enabled]),
            "disabled_modules": len(self._modules) - len([m for m, reg in self._modules.items() if reg.enabled]),
            "by_type": by_type,
            "by_health": by_health,
            "total_capabilities": sum(len(reg.metadata.capabilities) for reg in self._modules.values()),
        }
    
    def get_all_metadata(self) -> Dict[str, ModuleMetadata]:
        """Get all module metadata."""
        return {
            module_id: reg.metadata
            for module_id, reg in self._modules.items()
        }
    
    def get_dependencies(self, module_id: str) -> List[ModuleDependency]:
        """Get module dependencies."""
        metadata = self.get_metadata(module_id)
        
        if not metadata:
            return []
        
        return metadata.dependencies
    
    def check_dependencies_satisfied(self, module_id: str) -> tuple[bool, List[str]]:
        """Check if module dependencies are satisfied."""
        metadata = self.get_metadata(module_id)
        
        if not metadata:
            return False, ["Module not found"]
        
        missing = []
        
        for dep in metadata.dependencies:
            if dep.module_id not in self._modules:
                if dep.required:
                    missing.append(f"Required module {dep.module_id} not found")
            else:
                # Check version constraints
                dep_reg = self._modules[dep.module_id]
                dep_version = dep_reg.metadata.version
                
                if dep.min_version and dep_version < dep.min_version:
                    missing.append(f"Module {dep.module_id} version {dep_version} < {dep.min_version}")
                
                if dep.max_version and dep_version > dep.max_version:
                    missing.append(f"Module {dep.module_id} version {dep_version} > {dep.max_version}")
        
        return len(missing) == 0, missing
    
    def _lock(self):
        """Simple context manager for thread safety."""
        import threading
        return threading.Lock()


def create_module_registry() -> ModuleRegistry:
    """Factory function to create module registry."""
    return ModuleRegistry()


# Helper for creating module metadata
def create_module_metadata(
    module_id: str,
    name: str,
    version: str,
    module_type: ModuleType,
    description: str = "",
    author: str = "",
    tags: Optional[List[str]] = None,
) -> ModuleMetadata:
    """Create module metadata with common fields."""
    return ModuleMetadata(
        module_id=module_id,
        name=name,
        version=version,
        module_type=module_type,
        description=description,
        author=author,
        tags=tags or [],
    )
