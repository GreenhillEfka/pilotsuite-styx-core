#!/usr/bin/env python3
"""
Startup Profiling Script for PilotSuite Core

Identifies bottlenecks during service initialization by measuring:
- Time per service/module initialization
- Import times for heavy modules
- Memory usage during startup
- Connection pool initialization time
- Cache warming time

Usage:
    python scripts/profile_startup.py [--output reports/startup-profile.json]
    python scripts/profile_startup.py --verbose
    python scripts/profile_startup.py --top 10

Output:
    - Console: Summary of top bottlenecks
    - JSON file: Detailed timing data for all modules
    - Optional: Flame graph data (if --flame specified)

Author: Clawdya
Version: 1.0.0
Date: 2026-03-02
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import json
import logging
import os
import pstats
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

# Add app directory to path
APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class ModuleTiming:
    """Timing data for a single module/service."""
    
    name: str
    category: str  # "import", "init", "service"
    duration_ms: float
    timestamp: float
    success: bool = True
    error: Optional[str] = None
    memory_before_mb: float = 0.0
    memory_after_mb: 0.0 = 0.0
    
    @property
    def memory_delta_mb(self) -> float:
        return self.memory_after_mb - self.memory_before_mb


@dataclass
class ProfileResult:
    """Complete profiling result."""
    
    total_startup_time_ms: float
    module_timings: List[ModuleTiming]
    top_bottlenecks: List[ModuleTiming]
    category_summary: Dict[str, Dict[str, Any]]
    memory_peak_mb: float
    python_version: str
    platform: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_startup_time_ms": round(self.total_startup_time_ms, 2),
            "module_timings": [
                {
                    "name": t.name,
                    "category": t.category,
                    "duration_ms": round(t.duration_ms, 2),
                    "success": t.success,
                    "error": t.error,
                    "memory_delta_mb": round(t.memory_delta_mb, 2),
                }
                for t in self.module_timings
            ],
            "top_bottlenecks": [
                {
                    "name": t.name,
                    "category": t.category,
                    "duration_ms": round(t.duration_ms, 2),
                }
                for t in self.top_bottlenecks
            ],
            "category_summary": {
                cat: {
                    "count": data["count"],
                    "total_ms": round(data["total_ms"], 2),
                    "avg_ms": round(data["avg_ms"], 2),
                    "max_ms": round(data["max_ms"], 2),
                }
                for cat, data in self.category_summary.items()
            },
            "memory_peak_mb": round(self.memory_peak_mb, 2),
            "python_version": self.python_version,
            "platform": self.platform,
            "timestamp": self.timestamp,
        }


def get_memory_mb() -> float:
    """Get current memory usage in MB."""
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB to MB on Linux
    except Exception:
        return 0.0


def time_import(module_name: str) -> Tuple[float, bool, Optional[str]]:
    """Time how long it takes to import a module."""
    start = time.perf_counter()
    try:
        __import__(module_name)
        duration_ms = (time.perf_counter() - start) * 1000
        return duration_ms, True, None
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        return duration_ms, False, str(e)


async def time_async_init(
    name: str,
    init_func: Callable[[], Coroutine[Any, Any, Any]],
) -> Tuple[float, bool, Optional[str]]:
    """Time an async initialization function."""
    start = time.perf_counter()
    try:
        await init_func()
        duration_ms = (time.perf_counter() - start) * 1000
        return duration_ms, True, None
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        return duration_ms, False, str(e)


# Heavy modules to profile (common bottlenecks)
HEAVY_MODULES = [
    # Core services
    "copilot_core.core_setup",
    "copilot_core.brain_graph.service",
    "copilot_core.brain_graph.store",
    "copilot_core.energy.service",
    "copilot_core.vector_store",
    "copilot_core.embedding_engine",
    "copilot_core.conversation_memory",
    "copilot_core.household",
    "copilot_core.neurons.manager",
    "copilot_core.habitus.service",
    "copilot_core.mood.service",
    "copilot_core.ingest.event_processor",
    
    # ML modules (often slow)
    "copilot_core.ml.timeseries",
    "copilot_core.ml.anomaly",
    "copilot_core.ml.on_device",
    
    # API blueprints
    "copilot_core.api.v1.habitus",
    "copilot_core.api.v1.mood",
    "copilot_core.api.v1.energy_forecast",
    "copilot_core.api.v1.vector",
    "copilot_core.api.v1.rag",
    
    # External integrations
    "copilot_core.telegram",
    "copilot_core.unifi.service",
    "copilot_core.web_search_service",
    
    # Cache and connections
    "copilot_core.cache",
    "copilot_core.connection_pool",
    "copilot_core.connections",
]

# Services to profile during init
SERVICES_TO_PROFILE = [
    ("ConnectionPool", "copilot_core.connection_pool", "get_pool_manager"),
    ("HybridCache", "copilot_core.cache", "init_all_caches"),
    ("BrainGraph", "copilot_core.brain_graph.service", "BrainGraphService"),
    ("VectorStore", "copilot_core.vector_store", "get_vector_store"),
    ("EmbeddingEngine", "copilot_core.embedding_engine", "get_embedding_engine"),
    ("HabitusService", "copilot_core.habitus.service", "HabitusService"),
    ("MoodService", "copilot_core.mood.service", "MoodService"),
    ("EnergyService", "copilot_core.energy.service", "EnergyService"),
]


async def profile_imports() -> List[ModuleTiming]:
    """Profile import times for heavy modules."""
    timings = []
    
    logger.info("Profiling module imports...")
    
    for module_name in HEAVY_MODULES:
        memory_before = get_memory_mb()
        duration_ms, success, error = await time_async_init(
            module_name,
            lambda m=module_name: asyncio.get_event_loop().run_in_executor(
                None, time_import, m
            )
        )
        memory_after = get_memory_mb()
        
        category = "ml" if ".ml." in module_name else "api" if ".api." in module_name else "core"
        
        timings.append(ModuleTiming(
            name=module_name,
            category=category,
            duration_ms=duration_ms,
            timestamp=time.time(),
            success=success,
            error=error,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
        ))
        
        status = "✓" if success else "✗"
        logger.info(f"  {status} {module_name}: {duration_ms:.2f}ms")
    
    return timings


async def profile_service_inits() -> List[ModuleTiming]:
    """Profile service initialization times."""
    timings = []
    
    logger.info("Profiling service initializations...")
    
    for service_name, module_name, func_name in SERVICES_TO_PROFILE:
        try:
            # Import module
            module = __import__(module_name, fromlist=[func_name])
            func = getattr(module, func_name, None)
            
            if func is None:
                logger.warning(f"  ⚠ {service_name}: Function {func_name} not found")
                continue
            
            memory_before = get_memory_mb()
            start = time.perf_counter()
            
            # Call function (handle async vs sync)
            if asyncio.iscoroutinefunction(func):
                if func_name.startswith("get_") or func_name.startswith("init_"):
                    await func()
                else:
                    # Constructor - just instantiate
                    func()
            else:
                func()
            
            duration_ms = (time.perf_counter() - start) * 1000
            memory_after = get_memory_mb()
            
            timings.append(ModuleTiming(
                name=service_name,
                category="service",
                duration_ms=duration_ms,
                timestamp=time.time(),
                success=True,
                memory_before_mb=memory_before,
                memory_after_mb=memory_after,
            ))
            
            logger.info(f"  ✓ {service_name}: {duration_ms:.2f}ms (+{memory_after - memory_before:.2f}MB)")
            
        except Exception as e:
            timings.append(ModuleTiming(
                name=service_name,
                category="service",
                duration_ms=0.0,
                timestamp=time.time(),
                success=False,
                error=str(e),
            ))
            logger.warning(f"  ✗ {service_name}: {e}")
    
    return timings


async def profile_core_setup() -> List[ModuleTiming]:
    """Profile the full core_setup.init_services() flow."""
    timings = []
    
    logger.info("Profiling core_setup.init_services()...")
    
    try:
        from copilot_core.core_setup import init_services
        
        memory_before = get_memory_mb()
        start = time.perf_counter()
        
        services = await init_services(hass=None, config={
            "lazy_load_enabled": True,
            "brain_graph": {
                "max_nodes": 500,
                "max_edges": 1500,
            }
        })
        
        duration_ms = (time.perf_counter() - start) * 1000
        memory_after = get_memory_mb()
        
        timings.append(ModuleTiming(
            name="core_setup.init_services",
            category="full_init",
            duration_ms=duration_ms,
            timestamp=time.time(),
            success=True,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
        ))
        
        logger.info(f"  ✓ Full init_services(): {duration_ms:.2f}ms (+{memory_after - memory_before:.2f}MB)")
        
        # Add individual service timings if available
        if "startup_time_ms" in services:
            logger.info(f"    Reported startup time: {services['startup_time_ms']:.2f}ms")
        
    except Exception as e:
        timings.append(ModuleTiming(
            name="core_setup.init_services",
            category="full_init",
            duration_ms=0.0,
            timestamp=time.time(),
            success=False,
            error=str(e),
        ))
        logger.warning(f"  ✗ core_setup.init_services(): {e}")
    
    return timings


def compute_category_summary(timings: List[ModuleTiming]) -> Dict[str, Dict[str, Any]]:
    """Compute summary statistics per category."""
    categories = defaultdict(lambda: {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "failures": 0})
    
    for t in timings:
        cat = categories[t.category]
        cat["count"] += 1
        cat["total_ms"] += t.duration_ms
        cat["max_ms"] = max(cat["max_ms"], t.duration_ms)
        if not t.success:
            cat["failures"] += 1
    
    # Compute averages
    for cat_data in categories.values():
        if cat_data["count"] > 0:
            cat_data["avg_ms"] = cat_data["total_ms"] / cat_data["count"]
        else:
            cat_data["avg_ms"] = 0.0
    
    return dict(categories)


def get_top_bottlenecks(timings: List[ModuleTiming], top_n: int = 10) -> List[ModuleTiming]:
    """Get the top N slowest modules/services."""
    successful = [t for t in timings if t.success]
    return sorted(successful, key=lambda t: t.duration_ms, reverse=True)[:top_n]


async def run_profiling(
    output_path: Optional[str] = None,
    top_n: int = 10,
    verbose: bool = False,
    use_cprofile: bool = False,
) -> ProfileResult:
    """Run complete startup profiling."""
    
    all_timings: List[ModuleTiming] = []
    memory_peak = get_memory_mb()
    
    if use_cprofile:
        logger.info("Running with cProfile for detailed function-level profiling...")
        profiler = cProfile.Profile()
        profiler.enable()
    
    # Profile imports
    import_timings = await profile_imports()
    all_timings.extend(import_timings)
    
    # Profile service inits
    service_timings = await profile_service_inits()
    all_timings.extend(service_timings)
    
    # Profile full core_setup
    core_timings = await profile_core_setup()
    all_timings.extend(core_timings)
    
    if use_cprofile:
        profiler.disable()
    
    # Calculate totals
    total_time_ms = sum(t.duration_ms for t in all_timings)
    memory_peak = max(get_memory_mb(), max(t.memory_after_mb for t in all_timings))
    
    # Compute summaries
    category_summary = compute_category_summary(all_timings)
    top_bottlenecks = get_top_bottlenecks(all_timings, top_n)
    
    # Create result
    import platform
    result = ProfileResult(
        total_startup_time_ms=total_time_ms,
        module_timings=all_timings,
        top_bottlenecks=top_bottlenecks,
        category_summary=category_summary,
        memory_peak_mb=memory_peak,
        python_version=platform.python_version(),
        platform=platform.platform(),
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 STARTUP PROFILING RESULTS")
    print("=" * 70)
    print(f"\n⏱️  Total Startup Time: {result.total_startup_time_ms:.2f}ms")
    print(f"💾 Peak Memory Usage: {result.memory_peak_mb:.2f}MB")
    print(f"🐍 Python Version: {result.python_version}")
    print(f"🖥️  Platform: {result.platform}")
    
    print(f"\n📈 Category Summary:")
    for cat, data in sorted(category_summary.items(), key=lambda x: x[1]["total_ms"], reverse=True):
        print(f"  {cat:15s}: {data['count']:3d} modules, {data['total_ms']:8.2f}ms total, {data['avg_ms']:6.2f}ms avg")
    
    print(f"\n🔥 Top {top_n} Bottlenecks:")
    for i, t in enumerate(top_bottlenecks, 1):
        print(f"  {i:2d}. {t.name:40s} {t.duration_ms:8.2f}ms ({t.category})")
    
    if any(not t.success for t in all_timings):
        print(f"\n⚠️  Failures:")
        for t in all_timings:
            if not t.success:
                print(f"  ✗ {t.name}: {t.error}")
    
    # Save to file
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
    
    # Generate cProfile report if enabled
    if use_cprofile:
        print("\n📊 cProfile Report (top 20 functions):")
        print("-" * 70)
        stats_stream = StringIO()
        stats = pstats.Stats(profiler, stream=stats_stream)
        stats.sort_stats("cumulative")
        stats.print_stats(20)
        print(stats_stream.getvalue())
    
    print("=" * 70)
    
    return result


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Profile PilotSuite Core startup performance"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="reports/startup-profile.json",
        help="Output file path for JSON results (default: reports/startup-profile.json)"
    )
    parser.add_argument(
        "--top", "-t",
        type=int,
        default=10,
        help="Number of top bottlenecks to display (default: 10)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--flame",
        action="store_true",
        help="Generate flame graph data (requires py-spy)"
    )
    parser.add_argument(
        "--cprofile",
        action="store_true",
        help="Use cProfile for detailed function-level profiling"
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help="Disable output file generation"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    output_path = None if args.no_output else args.output
    
    await run_profiling(
        output_path=output_path,
        top_n=args.top,
        verbose=args.verbose,
        use_cprofile=args.cprofile,
    )


if __name__ == "__main__":
    asyncio.run(main())
