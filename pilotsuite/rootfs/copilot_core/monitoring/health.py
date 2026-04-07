"""
Extended Health Check Service for PilotSuite Styx Core

Provides comprehensive health checks for:
- System resources (CPU, Memory, Disk)
- Python dependencies
- External services (Home Assistant, Ollama, etc.)
- Internal modules and components
- Database/Storage health

Usage:
    from copilot_core.monitoring.health import HealthChecker
    
    checker = HealthChecker()
    health = await checker.full_health_check()
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import time
from typing import Any, Dict, List, Optional

import aiohttp
import psutil

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Comprehensive health check service.
    
    Checks:
    - System resources (CPU, Memory, Disk)
    - Python dependencies
    - External services (Home Assistant, Ollama, etc.)
    - Internal modules
    - Storage/database health
    """
    
    def __init__(
        self,
        ha_url: Optional[str] = None,
        ollama_url: Optional[str] = None,
        supervisor_url: Optional[str] = None,
    ):
        """
        Initialize health checker.
        
        Args:
            ha_url: Home Assistant API URL (e.g., http://supervisor/core)
            ollama_url: Ollama API URL (e.g., http://ollama:11434)
            supervisor_url: HA Supervisor URL (e.g., http://supervisor)
        """
        self.ha_url = ha_url or os.getenv("SUPERVISOR_URL", "http://supervisor/core")
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.supervisor_url = supervisor_url or os.getenv("SUPERVISOR_URL", "http://supervisor")
        
        # Define dependencies to check
        self.dependencies: List[Dict[str, str]] = [
            {"name": "prometheus_client", "type": "library", "required": True},
            {"name": "aiohttp", "type": "library", "required": True},
            {"name": "psutil", "type": "library", "required": True},
            {"name": "flask", "type": "library", "required": True},
            {"name": "waitress", "type": "library", "required": True},
        ]
        
        # Define external services to check
        self.external_services: List[Dict[str, Any]] = [
            {
                "name": "Home Assistant Core",
                "url": f"{self.ha_url}/api/config",
                "type": "service",
                "required": True,
                "timeout": 5,
            },
            {
                "name": "HA Supervisor",
                "url": f"{self.supervisor_url}/supervisor/ping",
                "type": "service",
                "required": False,
                "timeout": 3,
            },
            {
                "name": "Ollama",
                "url": f"{self.ollama_url}/api/tags",
                "type": "service",
                "required": False,
                "timeout": 5,
            },
        ]
        
        # Define internal modules to check
        self.internal_modules: List[Dict[str, str]] = [
            {"name": "copilot_core.base", "type": "module"},
            {"name": "copilot_core.config", "type": "module"},
            {"name": "copilot_core.connection_pool", "type": "module"},
            {"name": "copilot_core.llm_provider", "type": "module"},
            {"name": "copilot_core.cache", "type": "module"},
            {"name": "copilot_core.monitoring.metrics", "type": "module"},
        ]
        
        # Storage paths to check
        self.storage_paths: List[Dict[str, Any]] = [
            {"path": "/data", "name": "Data Directory", "required": True},
            {"path": "/data/brain_graph.json", "name": "Brain Graph", "required": False},
            {"path": "/data/events.jsonl", "name": "Events Log", "required": False},
            {"path": "/data/candidates.json", "name": "Candidates Cache", "required": False},
        ]
        
        # Thresholds for warnings
        self.thresholds = {
            "cpu_warning": 80,
            "cpu_critical": 95,
            "memory_warning": 80,
            "memory_critical": 95,
            "disk_warning": 80,
            "disk_critical": 95,
        }
    
    def _check_library(self, name: str) -> bool:
        """Check if a Python library is installed and importable."""
        try:
            return importlib.util.find_spec(name) is not None
        except Exception as e:
            logger.warning(f"Failed to check library {name}: {e}")
            return False
    
    def _check_module(self, module_path: str) -> bool:
        """Check if an internal module can be imported."""
        try:
            importlib.import_module(module_path)
            return True
        except Exception as e:
            logger.warning(f"Failed to import module {module_path}: {e}")
            return False
    
    def _check_storage_path(self, path: str) -> Dict[str, Any]:
        """Check if a storage path exists and is writable."""
        result = {
            "exists": os.path.exists(path),
            "writable": False,
            "size_bytes": None,
        }
        
        if os.path.exists(path):
            if os.path.isfile(path):
                try:
                    result["size_bytes"] = os.path.getsize(path)
                except Exception:
                    pass
            elif os.path.isdir(path):
                try:
                    # Check if writable by creating a temp file
                    test_file = os.path.join(path, ".health_check_test")
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    result["writable"] = True
                except Exception as e:
                    logger.warning(f"Storage path {path} not writable: {e}")
        
        return result
    
    async def _check_service(
        self, name: str, url: str, timeout: int = 5
    ) -> Dict[str, Any]:
        """Check if an external service is reachable."""
        result = {
            "reachable": False,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
        }
        
        try:
            start = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    result["reachable"] = response.status < 500
                    result["status_code"] = response.status
                    result["response_time_ms"] = round((time.time() - start) * 1000, 2)
        except asyncio.TimeoutError:
            result["error"] = f"Timeout after {timeout}s"
        except aiohttp.ClientError as e:
            result["error"] = str(e)
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
        
        return result
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system resource health metrics."""
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        # Determine status based on thresholds
        status = "healthy"
        issues = []
        
        if cpu_usage > self.thresholds["cpu_critical"]:
            status = "critical"
            issues.append(f"CPU usage critical: {cpu_usage}%")
        elif cpu_usage > self.thresholds["cpu_warning"]:
            if status != "critical":
                status = "degraded"
            issues.append(f"CPU usage high: {cpu_usage}%")
        
        if memory.percent > self.thresholds["memory_critical"]:
            status = "critical"
            issues.append(f"Memory usage critical: {memory.percent}%")
        elif memory.percent > self.thresholds["memory_warning"]:
            if status != "critical":
                status = "degraded"
            issues.append(f"Memory usage high: {memory.percent}%")
        
        if disk.percent > self.thresholds["disk_critical"]:
            status = "critical"
            issues.append(f"Disk usage critical: {disk.percent}%")
        elif disk.percent > self.thresholds["disk_warning"]:
            if status != "critical":
                status = "degraded"
            issues.append(f"Disk usage high: {disk.percent}%")
        
        return {
            "status": status,
            "issues": issues,
            "metrics": {
                "cpu_percent": cpu_usage,
                "memory_percent": memory.percent,
                "memory_available_bytes": memory.available,
                "memory_total_bytes": memory.total,
                "disk_percent": disk.percent,
                "disk_free_bytes": disk.free,
                "disk_total_bytes": disk.total,
            },
        }
    
    async def get_dependency_health(self) -> Dict[str, Any]:
        """Check status of all Python dependencies."""
        results = {}
        missing_required = []
        
        for dep in self.dependencies:
            is_healthy = self._check_library(dep["name"])
            status = "healthy" if is_healthy else "missing"
            
            if not is_healthy and dep.get("required", False):
                missing_required.append(dep["name"])
            
            results[dep["name"]] = {
                "status": status,
                "type": dep["type"],
                "required": dep.get("required", False),
            }
        
        overall_status = "healthy" if not missing_required else "unhealthy"
        
        return {
            "status": overall_status,
            "missing_required": missing_required,
            "dependencies": results,
        }
    
    async def get_module_health(self) -> Dict[str, Any]:
        """Check status of internal modules."""
        results = {}
        failed_modules = []
        
        for module in self.internal_modules:
            is_healthy = self._check_module(module["name"])
            status = "healthy" if is_healthy else "failed"
            
            if not is_healthy:
                failed_modules.append(module["name"])
            
            results[module["name"]] = {
                "status": status,
                "type": module["type"],
            }
        
        overall_status = "healthy" if not failed_modules else "degraded"
        
        return {
            "status": overall_status,
            "failed_modules": failed_modules,
            "modules": results,
        }
    
    async def get_storage_health(self) -> Dict[str, Any]:
        """Check storage paths health."""
        results = {}
        issues = []
        
        for storage in self.storage_paths:
            check = self._check_storage_path(storage["path"])
            
            if storage["required"] and not check["exists"]:
                issues.append(f"Required storage missing: {storage['name']}")
            
            results[storage["name"]] = {
                "path": storage["path"],
                "exists": check["exists"],
                "required": storage["required"],
                **check,
            }
        
        overall_status = "healthy" if not issues else "degraded"
        
        return {
            "status": overall_status,
            "issues": issues,
            "storage": results,
        }
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Check external service health."""
        results = {}
        unreachable_required = []
        
        # Check services in parallel
        tasks = []
        for service in self.external_services:
            task = self._check_service(
                service["name"],
                service["url"],
                service.get("timeout", 5),
            )
            tasks.append(task)
        
        service_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for service, result in zip(self.external_services, service_results):
            if isinstance(result, Exception):
                results[service["name"]] = {
                    "status": "error",
                    "error": str(result),
                    "required": service.get("required", False),
                }
                if service.get("required", False):
                    unreachable_required.append(service["name"])
            else:
                status = "healthy" if result["reachable"] else "unreachable"
                results[service["name"]] = {
                    "status": status,
                    **result,
                    "required": service.get("required", False),
                }
                if not result["reachable"] and service.get("required", False):
                    unreachable_required.append(service["name"])
        
        overall_status = "healthy" if not unreachable_required else "unhealthy"
        
        return {
            "status": overall_status,
            "unreachable_required": unreachable_required,
            "services": results,
        }
    
    async def full_health_check(self) -> Dict[str, Any]:
        """
        Run a complete health check across all components.
        
        Returns:
            dict: Comprehensive health status with all components
        """
        start_time = time.time()
        
        # Run all checks in parallel
        tasks = [
            self.get_system_health(),
            self.get_dependency_health(),
            self.get_module_health(),
            self.get_storage_health(),
            self.get_service_health(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Parse results
        system_health = results[0] if not isinstance(results[0], Exception) else {"status": "error"}
        dependency_health = results[1] if not isinstance(results[1], Exception) else {"status": "error"}
        module_health = results[2] if not isinstance(results[2], Exception) else {"status": "error"}
        storage_health = results[3] if not isinstance(results[3], Exception) else {"status": "error"}
        service_health = results[4] if not isinstance(results[4], Exception) else {"status": "error"}
        
        # Determine overall status
        statuses = [
            system_health.get("status", "unknown"),
            dependency_health.get("status", "unknown"),
            module_health.get("status", "unknown"),
            storage_health.get("status", "unknown"),
            service_health.get("status", "unknown"),
        ]
        
        if "critical" in statuses or "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses:
            overall_status = "degraded"
        elif "error" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        return {
            "status": overall_status,
            "timestamp": time.time(),
            "duration_ms": duration_ms,
            "components": {
                "system": system_health,
                "dependencies": dependency_health,
                "modules": module_health,
                "storage": storage_health,
                "services": service_health,
            },
        }
    
    async def get_quick_health(self) -> Dict[str, Any]:
        """
        Quick health check (system + dependencies only).
        
        Faster than full_health_check, skips external services.
        """
        start_time = time.time()
        
        system_health = await self.get_system_health()
        dependency_health = await self.get_dependency_health()
        
        statuses = [
            system_health.get("status", "unknown"),
            dependency_health.get("status", "unknown"),
        ]
        
        if "critical" in statuses or "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "timestamp": time.time(),
            "duration_ms": round((time.time() - start_time) * 1000, 2),
            "system": system_health,
            "dependencies": dependency_health,
        }


# Global instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker(
    ha_url: Optional[str] = None,
    ollama_url: Optional[str] = None,
    supervisor_url: Optional[str] = None,
) -> HealthChecker:
    """Get or create the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(
            ha_url=ha_url,
            ollama_url=ollama_url,
            supervisor_url=supervisor_url,
        )
    return _health_checker
