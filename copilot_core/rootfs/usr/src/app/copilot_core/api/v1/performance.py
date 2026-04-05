"""
Performance Metrics API Blueprint

Provides endpoints for monitoring and analyzing application performance:
- Startup time metrics
- Memory usage per module
- Lazy loading statistics
- Real-time performance monitoring

Usage:
    from copilot_core.api.v1.performance import performance_bp
    app.register_blueprint(performance_bp, url_prefix="/api/v1")
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Create blueprint
performance_bp = Blueprint("performance", __name__)


@dataclass
class StartupMetrics:
    """Startup performance metrics."""
    total_startup_time_ms: float = 0.0
    lazy_load_enabled: bool = True
    modules_loaded_count: int = 0
    modules_deferred_count: int = 0
    target_startup_time_ms: float = 2000.0
    actual_startup_time_ms: float = 0.0
    performance_achieved: bool = False
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ModuleMetrics:
    """Individual module performance metrics."""
    name: str
    load_time_ms: float
    memory_delta_mb: float
    loaded_at: float
    accessed_count: int
    is_lazy_loaded: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)


class PerformanceTracker:
    """
    Tracks performance metrics for the application.
    
    Singleton pattern for global access.
    """
    
    _instance: Optional["PerformanceTracker"] = None
    _lock = None
    
    def __new__(cls) -> "PerformanceTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._startup_metrics = StartupMetrics()
        self._module_metrics: Dict[str, ModuleMetrics] = {}
        self._start_time: float = 0.0
        self._initialized = True
        
        import threading
        self._lock = threading.RLock()
    
    def start_startup_timer(self) -> None:
        """Start the startup timer."""
        self._start_time = time.perf_counter()
        logger.debug("Startup timer started")
    
    def record_startup_complete(
        self,
        lazy_load_enabled: bool = True,
        modules_loaded: int = 0,
        modules_deferred: int = 0,
    ) -> StartupMetrics:
        """
        Record startup completion and calculate metrics.
        
        Args:
            lazy_load_enabled: Whether lazy loading was enabled
            modules_loaded: Number of modules loaded during startup
            modules_deferred: Number of modules deferred via lazy loading
        
        Returns:
            StartupMetrics instance
        """
        if self._start_time == 0:
            logger.warning("Startup timer was not started")
            self._start_time = time.perf_counter()
        
        elapsed_ms = (time.perf_counter() - self._start_time) * 1000
        
        with self._lock:
            self._startup_metrics = StartupMetrics(
                total_startup_time_ms=elapsed_ms,
                lazy_load_enabled=lazy_load_enabled,
                modules_loaded_count=modules_loaded,
                modules_deferred_count=modules_deferred,
                target_startup_time_ms=2000.0,
                actual_startup_time_ms=elapsed_ms,
                performance_achieved=elapsed_ms < 2000.0,
            )
        
        logger.info(
            f"Startup completed in {elapsed_ms:.2f}ms "
            f"(target: 2000ms, achieved: {self._startup_metrics.performance_achieved})"
        )
        
        return self._startup_metrics
    
    def register_module_load(
        self,
        name: str,
        load_time_ms: float,
        memory_delta_mb: float,
        is_lazy_loaded: bool = True,
    ) -> None:
        """
        Register a module load event.
        
        Args:
            name: Module name
            load_time_ms: Time taken to load in milliseconds
            memory_delta_mb: Memory increase in MB
            is_lazy_loaded: Whether this was a lazy-loaded module
        """
        with self._lock:
            self._module_metrics[name] = ModuleMetrics(
                name=name,
                load_time_ms=load_time_ms,
                memory_delta_mb=memory_delta_mb,
                loaded_at=time.time(),
                accessed_count=1,
                is_lazy_loaded=is_lazy_loaded,
            )
        
        logger.debug(
            f"Module {name} loaded: {load_time_ms:.2f}ms, "
            f"memory delta: {memory_delta_mb:.2f}MB"
        )
    
    def get_startup_metrics(self) -> StartupMetrics:
        """Get current startup metrics."""
        with self._lock:
            return self._startup_metrics
    
    def get_module_metrics(self) -> List[ModuleMetrics]:
        """Get all module metrics."""
        with self._lock:
            return list(self._module_metrics.values())
    
    def get_summary(self) -> dict:
        """Get a summary of all performance metrics."""
        with self._lock:
            startup = self._startup_metrics
            modules = list(self._module_metrics.values())
            
            total_load_time = sum(m.load_time_ms for m in modules)
            total_memory = sum(m.memory_delta_mb for m in modules)
            lazy_loaded_count = sum(1 for m in modules if m.is_lazy_loaded)
            
            return {
                "startup": startup.to_dict(),
                "modules": {
                    "total_count": len(modules),
                    "lazy_loaded_count": lazy_loaded_count,
                    "eager_loaded_count": len(modules) - lazy_loaded_count,
                    "total_load_time_ms": total_load_time,
                    "total_memory_mb": total_memory,
                },
                "performance": {
                    "startup_target_met": startup.performance_achieved,
                    "startup_time_ms": startup.actual_startup_time_ms,
                    "startup_target_ms": startup.target_startup_time_ms,
                    "improvement_vs_eager": self._calculate_improvement(),
                },
            }
    
    def _calculate_improvement(self) -> dict:
        """Calculate performance improvement vs eager loading."""
        # Estimate what startup would have been without lazy loading
        with self._lock:
            modules = list(self._module_metrics.values())
            deferred_modules = [m for m in modules if m.is_lazy_loaded]
            
            if not deferred_modules:
                return {
                    "estimated_eager_time_ms": self._startup_metrics.actual_startup_time_ms,
                    "actual_lazy_time_ms": self._startup_metrics.actual_startup_time_ms,
                    "time_saved_ms": 0,
                    "improvement_percent": 0,
                }
            
            # Sum up deferred module load times
            deferred_time = sum(m.load_time_ms for m in deferred_modules)
            estimated_eager = self._startup_metrics.actual_startup_time_ms + deferred_time
            time_saved = deferred_time
            improvement = (time_saved / estimated_eager * 100) if estimated_eager > 0 else 0
            
            return {
                "estimated_eager_time_ms": estimated_eager,
                "actual_lazy_time_ms": self._startup_metrics.actual_startup_time_ms,
                "time_saved_ms": time_saved,
                "improvement_percent": round(improvement, 2),
            }


# Global tracker instance
_tracker: Optional[PerformanceTracker] = None


def _error_response(message: str, status_code: int = 400):
    return jsonify({
        "success": False,
        "error": message,
    }), status_code


def _parse_bool_arg(name: str, default: bool = False) -> bool:
    raw = request.args.get(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{name} must be 'true' or 'false'")


def _get_json_object(*, allow_empty: bool = True) -> Dict[str, Any]:
    data = request.get_json(silent=True)

    if data is None:
        raw_body = request.get_data(cache=True) or b""
        if allow_empty and not raw_body.strip():
            return {}
        raise ValueError("JSON body must be an object")

    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")

    return data


def _require_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker


def init_performance_api(tracker: Optional[Any] = None) -> Any:
    """Reset or inject the tracker used by the performance API."""
    global _tracker

    if tracker is None:
        PerformanceTracker._instance = None
        tracker = PerformanceTracker()

    _tracker = tracker
    return tracker


@performance_bp.route("/performance/startup", methods=["GET"])
def get_startup_performance():
    """
    Get startup performance metrics.
    
    Returns:
        JSON with startup time, lazy loading status, and target achievement
    """
    try:
        tracker = get_performance_tracker()
        metrics = tracker.get_startup_metrics()
        
        return jsonify({
            "success": True,
            "metrics": metrics.to_dict(),
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get startup metrics: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@performance_bp.route("/performance/modules", methods=["GET"])
def get_module_performance():
    """
    Get per-module performance metrics.
    
    Query params:
    - lazy_only: If "true", only return lazy-loaded modules
    
    Returns:
        JSON array of module metrics
    """
    try:
        lazy_only = _parse_bool_arg("lazy_only", default=False)

        tracker = get_performance_tracker()
        modules = tracker.get_module_metrics()

        if lazy_only:
            modules = [m for m in modules if m.is_lazy_loaded]

        return jsonify({
            "success": True,
            "count": len(modules),
            "modules": [m.to_dict() for m in modules],
        }), 200

    except ValueError as exc:
        return _error_response(str(exc), 400)

    except Exception as e:
        logger.error(f"Failed to get module metrics: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@performance_bp.route("/performance/summary", methods=["GET"])
def get_performance_summary():
    """
    Get comprehensive performance summary.
    
    Returns:
        JSON with startup, module, and improvement metrics
    """
    try:
        tracker = get_performance_tracker()
        summary = tracker.get_summary()
        
        return jsonify({
            "success": True,
            "summary": summary,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get performance summary: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@performance_bp.route("/performance/lazy-load/status", methods=["GET"])
def get_lazy_load_status():
    """
    Get lazy loading status and statistics.
    
    Returns:
        JSON with lazy loading configuration and statistics
    """
    try:
        from copilot_core.utils.lazy_loader import LazyLoader
        
        tracker = get_performance_tracker()
        modules = tracker.get_module_metrics()
        
        loaded_count = sum(1 for m in modules if m.is_lazy_loaded)
        total_accesses = sum(m.accessed_count for m in modules)
        
        return jsonify({
            "success": True,
            "lazy_load": {
                "enabled": LazyLoader.is_enabled(),
                "modules_registered": len(modules),
                "modules_loaded": loaded_count,
                "modules_still_deferred": len(modules) - loaded_count,
                "total_accesses": total_accesses,
                "total_load_time_ms": sum(m.load_time_ms for m in modules),
                "total_memory_mb": sum(m.memory_delta_mb for m in modules),
            },
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get lazy load status: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@performance_bp.route("/performance/benchmark", methods=["POST"])
def run_benchmark():
    """
    Run a performance benchmark.
    
    Body (optional):
    - iterations: Number of iterations (default: 10)
    - include_modules: Whether to include module loading (default: true)
    
    Returns:
        JSON with benchmark results
    """
    try:
        data = _get_json_object(allow_empty=True)
        iterations = _require_positive_int(data.get("iterations", 10), "iterations")
        include_modules = _require_bool(data.get("include_modules", True), "include_modules")

        results = {
            "iterations": iterations,
            "startup_times_ms": [],
            "module_load_times_ms": [],
        }
        
        for i in range(iterations):
            # Simulate startup timing
            start = time.perf_counter()
            
            if include_modules:
                # Import and measure module loading
                from copilot_core.utils.lazy_loader import LazyLoader
                LazyLoader.reset_all()
                
                # Load a sample of modules
                from copilot_core.utils.lazy_loader import (
                    energy_service_loader,
                    ml_transformer_loader,
                    proactive_engine_loader,
                )
                
                # Force load to measure
                energy_service_loader.load()
                ml_transformer_loader.load()
                proactive_engine_loader.load()
                
                module_times = [
                    energy_service_loader.metrics.load_time_ms,
                    ml_transformer_loader.metrics.load_time_ms,
                    proactive_engine_loader.metrics.load_time_ms,
                ]
                results["module_load_times_ms"].append(module_times)
            
            elapsed = (time.perf_counter() - start) * 1000
            results["startup_times_ms"].append(elapsed)
        
        # Calculate statistics
        import statistics
        
        startup_avg = statistics.mean(results["startup_times_ms"])
        startup_min = min(results["startup_times_ms"])
        startup_max = max(results["startup_times_ms"])
        startup_std = statistics.stdev(results["startup_times_ms"]) if len(results["startup_times_ms"]) > 1 else 0
        
        benchmark_result = {
            "success": True,
            "benchmark": {
                "iterations": iterations,
                "startup": {
                    "average_ms": round(startup_avg, 2),
                    "min_ms": round(startup_min, 2),
                    "max_ms": round(startup_max, 2),
                    "std_dev_ms": round(startup_std, 2),
                },
                "target_met": startup_avg < 2000.0,
                "target_ms": 2000.0,
            },
        }
        
        return jsonify(benchmark_result), 200

    except ValueError as exc:
        return _error_response(str(exc), 400)

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@performance_bp.route("/performance/health", methods=["GET"])
def performance_health():
    """
    Quick performance health check.
    
    Returns:
        JSON with basic performance health status
    """
    try:
        tracker = get_performance_tracker()
        startup = tracker.get_startup_metrics()
        
        health_status = "healthy"
        issues = []
        
        if not startup.performance_achieved:
            health_status = "degraded"
            issues.append(f"Startup time {startup.actual_startup_time_ms:.0f}ms exceeds target 2000ms")
        
        return jsonify({
            "success": True,
            "health": {
                "status": health_status,
                "startup_time_ms": round(startup.actual_startup_time_ms, 2),
                "target_ms": startup.target_startup_time_ms,
                "target_met": startup.performance_achieved,
                "issues": issues,
            },
        }), 200
        
    except Exception as e:
        logger.error(f"Performance health check failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
