"""
Lazy Loader for PilotSuite Styx Core Modules

Provides deferred loading of heavy modules to optimize startup time.
Modules are only loaded when first accessed, reducing initial memory footprint
and startup latency.

Usage:
    from copilot_core.utils.lazy_loader import LazyLoader
    
    # Defer loading of heavy modules
    energy_service = LazyLoader(
        "energy_service",
        "copilot_core.energy.service",
        "EnergyService"
    )
    
    # Module loads automatically on first access
    service = energy_service(hass)  # Loads here on first call
    
    # Or explicitly load
    energy_service.load()
    
Features:
    - Transparent proxy: works like the actual module/class
    - Thread-safe loading
    - Configurable via lazy_load_enabled flag
    - Tracks load time and memory for performance metrics
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
from typing import Any, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModuleLoadMetrics:
    """Metrics for a lazily loaded module."""
    module_name: str
    load_time_ms: float = 0.0
    memory_before_bytes: int = 0
    memory_after_bytes: int = 0
    loaded_at: float = 0.0
    accessed_count: int = 0
    
    @property
    def memory_delta_bytes(self) -> int:
        """Memory increase due to loading this module."""
        return self.memory_after_bytes - self.memory_before_bytes
    
    @property
    def memory_delta_mb(self) -> float:
        """Memory increase in MB."""
        return self.memory_delta_bytes / (1024 * 1024)


class LazyLoader:
    """
    Lazy loader for deferring module imports.
    
    Acts as a transparent proxy that loads the target module on first access.
    Tracks performance metrics for monitoring and optimization.
    """
    
    _global_enabled: bool = True
    _all_loaders: list["LazyLoader"] = []
    _lock = threading.Lock()
    
    def __init__(
        self,
        name: str,
        module_path: str,
        attribute: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Initialize a lazy loader.
        
        Args:
            name: Human-readable name for this loader (for metrics/logging)
            module_path: Full module path (e.g., "copilot_core.energy.service")
            attribute: Optional attribute to extract from module (e.g., "EnergyService")
            description: Optional description for documentation
        """
        self.name = name
        self.module_path = module_path
        self.attribute = attribute
        self.description = description or f"Lazy loader for {module_path}"
        
        self._module: Optional[Any] = None
        self._loaded: bool = False
        self._lock = threading.Lock()
        self._metrics = ModuleLoadMetrics(module_name=name)
        
        # Register globally for metrics collection
        with LazyLoader._lock:
            LazyLoader._all_loaders.append(self)
    
    @classmethod
    def enable(cls) -> None:
        """Enable lazy loading globally."""
        cls._global_enabled = True
        logger.info("Lazy loading enabled globally")
    
    @classmethod
    def disable(cls) -> None:
        """Disable lazy loading globally (load all modules immediately)."""
        cls._global_enabled = False
        logger.info("Lazy loading disabled globally - preloading all modules")
        # Preload all registered loaders
        with cls._lock:
            for loader in cls._all_loaders:
                loader.load()
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if lazy loading is enabled globally."""
        return cls._global_enabled
    
    @classmethod
    def get_all_metrics(cls) -> list[ModuleLoadMetrics]:
        """Get metrics for all lazy loaders."""
        with cls._lock:
            return [loader._metrics.copy() for loader in cls._all_loaders if loader._loaded]
    
    @classmethod
    def get_total_load_time_ms(cls) -> float:
        """Get total time spent loading all modules."""
        with cls._lock:
            return sum(m.load_time_ms for m in cls.get_all_metrics())
    
    @classmethod
    def get_total_memory_delta_mb(cls) -> float:
        """Get total memory increase from all loaded modules."""
        with cls._lock:
            return sum(m.memory_delta_mb for m in cls.get_all_metrics())
    
    @classmethod
    def reset_all(cls) -> None:
        """Reset all loaders (for testing)."""
        with cls._lock:
            for loader in cls._all_loaders:
                loader._module = None
                loader._loaded = False
                loader._metrics = ModuleLoadMetrics(module_name=loader.name)
    
    def _get_memory_usage(self) -> int:
        """Get current process memory usage in bytes."""
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        except ImportError:
            # Fallback for systems without resource module
            try:
                import psutil
                import os
                return psutil.Process(os.getpid()).memory_info().rss
            except ImportError:
                return 0
    
    def load(self) -> Any:
        """
        Force load the module immediately.
        
        Returns:
            The loaded module or attribute.
        """
        with self._lock:
            if self._loaded:
                return self._module
            
            if not LazyLoader._global_enabled:
                # Lazy loading disabled, load immediately
                logger.debug(f"Lazy loading disabled, preloading {self.name}")
            
            logger.debug(f"Loading module: {self.module_path} (attribute: {self.attribute})")
            
            # Capture memory before loading
            self._metrics.memory_before_bytes = self._get_memory_usage()
            start_time = time.perf_counter()
            
            try:
                # Import the module
                module = importlib.import_module(self.module_path)
                
                # Extract attribute if specified
                if self.attribute:
                    result = getattr(module, self.attribute)
                else:
                    result = module
                
                # Capture metrics after loading
                end_time = time.perf_counter()
                self._metrics.memory_after_bytes = self._get_memory_usage()
                self._metrics.load_time_ms = (end_time - start_time) * 1000
                self._metrics.loaded_at = time.time()
                
                self._module = result
                self._loaded = True
                
                logger.info(
                    f"Loaded {self.name}: {self._metrics.load_time_ms:.2f}ms, "
                    f"memory delta: {self._metrics.memory_delta_mb:.2f}MB"
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to load module {self.module_path}: {e}")
                raise
    
    def __getattr__(self, name: str) -> Any:
        """
        Proxy attribute access to the loaded module.
        
        Triggers lazy loading on first access.
        """
        if name.startswith('_'):
            # Don't trigger loading for private attributes
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        
        # Load module on first access
        if not self._loaded:
            self.load()
        
        self._metrics.accessed_count += 1
        
        # Access the attribute on the loaded module
        return getattr(self._module, name)
    
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Proxy call to the loaded module/class.
        
        Triggers lazy loading on first call.
        """
        if not self._loaded:
            self.load()
        
        self._metrics.accessed_count += 1
        
        # Call the loaded module/class
        return self._module(*args, **kwargs)
    
    def __repr__(self) -> str:
        status = "loaded" if self._loaded else "deferred"
        return f"<LazyLoader {self.name} ({status})>"
    
    @property
    def is_loaded(self) -> bool:
        """Check if this module has been loaded."""
        return self._loaded
    
    @property
    def metrics(self) -> ModuleLoadMetrics:
        """Get metrics for this loader."""
        return self._metrics


def create_lazy_module(
    name: str,
    module_path: str,
    description: Optional[str] = None,
) -> LazyLoader:
    """
    Create a lazy loader for an entire module.
    
    Args:
        name: Human-readable name
        module_path: Full module path
        description: Optional description
    
    Returns:
        LazyLoader instance
    """
    return LazyLoader(name, module_path, attribute=None, description=description)


def create_lazy_class(
    name: str,
    module_path: str,
    class_name: str,
    description: Optional[str] = None,
) -> LazyLoader:
    """
    Create a lazy loader for a specific class.
    
    Args:
        name: Human-readable name
        module_path: Module containing the class
        class_name: Name of the class to load
        description: Optional description
    
    Returns:
        LazyLoader instance
    """
    return LazyLoader(name, module_path, attribute=class_name, description=description)


# Pre-defined lazy loaders for heavy PilotSuite modules
# These can be imported and used directly in core_setup.py

energy_service_loader = create_lazy_class(
    "energy_service",
    "copilot_core.energy.service",
    "EnergyService",
    "Energy forecasting and load shifting service"
)

ml_transformer_loader = create_lazy_class(
    "ml_transformer",
    "copilot_core.ml.transformer_model",
    "TransformerModel",
    "ML transformer model for predictions"
)

ml_lstm_loader = create_lazy_class(
    "ml_lstm",
    "copilot_core.ml.lstm_forecast",
    "LSTMForecaster",
    "ML LSTM forecaster"
)

calendar_service_loader = create_lazy_class(
    "calendar_service",
    "copilot_core.calendar.service",
    "CalendarService",
    "Calendar integration service"
)

proactive_engine_loader = create_lazy_class(
    "proactive_engine",
    "copilot_core.proactive_engine",
    "ProactiveContextEngine",
    "Proactive context engine"
)

web_search_loader = create_lazy_class(
    "web_search",
    "copilot_core.web_search",
    "WebSearchService",
    "Web search service"
)
