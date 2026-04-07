"""Edge Computing — Local Processing, Offline Mode, Sync Engine."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import time
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Sync status types."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class EdgeOperation:
    """Operation to be synced."""
    id: str
    operation_type: str
    payload: Dict[str, Any]
    timestamp: float
    device_id: str
    synced: bool = False
    retry_count: int = 0


@dataclass
class EdgeDevice:
    """Edge device configuration."""
    id: str
    name: str
    capabilities: List[str]
    compute_power: str  # low, medium, high
    storage_mb: int
    online: bool = False
    last_seen: Optional[float] = None


class EdgeComputingEngine:
    """Edge computing engine for local processing."""

    def __init__(self, storage_path: str = "/tmp/edge_storage"):
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._devices: Dict[str, EdgeDevice] = {}
        self._pending_ops: Dict[str, EdgeOperation] = {}
        self._sync_queue: List[EdgeOperation] = []
        self._local_cache: Dict[str, Any] = {}
        self._offline_mode: bool = False
        self._sync_handlers: Dict[str, Callable] = {}
        self._device_id: str = "edge_device_1"

    def register_device(self, device: EdgeDevice) -> str:
        """Register an edge device."""
        self._devices[device.id] = device
        logger.info(f"Edge device registered: {device.name} ({device.id})")
        return device.id

    def set_offline_mode(self, offline: bool):
        """Enable/disable offline mode."""
        self._offline_mode = offline
        logger.info(f"Offline mode: {'enabled' if offline else 'disabled'}")

    def execute_local(self, operation_type: str, payload: Dict) -> Dict[str, Any]:
        """Execute an operation locally on edge device."""
        logger.info(f"Executing locally: {operation_type}")
        
        # Simulated local execution
        result = {
            "success": True,
            "operation": operation_type,
            "timestamp": time.time(),
            "device_id": self._device_id,
            "result": payload,
        }
        
        # Store in local cache
        cache_key = f"{operation_type}_{int(time.time())}"
        self._local_cache[cache_key] = result
        
        # Queue for sync if not offline
        if not self._offline_mode:
            op = EdgeOperation(
                id=cache_key,
                operation_type=operation_type,
                payload=payload,
                timestamp=time.time(),
                device_id=self._device_id,
            )
            self._pending_ops[cache_key] = op
            self._sync_queue.append(op)
        
        return result

    def sync_pending_operations(self) -> Dict[str, Any]:
        """Sync pending operations to cloud/central."""
        if self._offline_mode:
            return {"status": "offline", "pending": len(self._sync_queue)}
        
        synced = 0
        failed = 0
        conflicts = 0
        
        for op in self._sync_queue[:]:
            try:
                # Simulated sync
                # In production, would send to central server
                op.synced = True
                synced += 1
                self._sync_queue.remove(op)
                
            except Exception as e:
                if "conflict" in str(e).lower():
                    conflicts += 1
                    op.retry_count += 1
                else:
                    failed += 1
                    op.retry_count += 1
        
        logger.info(f"Sync complete: {synced} synced, {failed} failed, {conflicts} conflicts")
        
        return {
            "status": "synced",
            "synced": synced,
            "failed": failed,
            "conflicts": conflicts,
            "remaining": len(self._sync_queue),
        }

    def get_local_data(self, key: str) -> Optional[Any]:
        """Get data from local cache."""
        return self._local_cache.get(key)

    def persist_to_disk(self, key: str, data: Any) -> bool:
        """Persist data to local disk storage."""
        try:
            file_path = self._storage_path / f"{key}.json"
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Data persisted: {key}")
            return True
        except Exception as e:
            logger.error(f"Persist failed: {e}")
            return False

    def load_from_disk(self, key: str) -> Optional[Any]:
        """Load data from local disk storage."""
        file_path = self._storage_path / f"{key}.json"
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Load failed: {e}")
            return None

    def distribute_compute(self, task: Dict, target_devices: Optional[List[str]] = None) -> Dict:
        """Distribute compute task across edge devices."""
        devices = target_devices or [d.id for d in self._devices.values() if d.online]
        
        if not devices:
            return {"status": "no_devices", "task": task}
        
        # Simple round-robin distribution
        results = {}
        for i, device_id in enumerate(devices):
            device = self._devices.get(device_id)
            if not device:
                continue
            
            # Assign task based on device capabilities
            results[device_id] = {
                "task_id": f"task_{i}",
                "status": "assigned",
                "device": device.name,
            }
        
        logger.info(f"Task distributed to {len(results)} devices")
        return {
            "status": "distributed",
            "devices": len(results),
            "results": results,
        }

    def get_edge_health(self) -> Dict[str, Any]:
        """Get edge computing health status."""
        online_devices = len([d for d in self._devices.values() if d.online])
        pending_ops = len(self._sync_queue)
        
        return {
            "offline_mode": self._offline_mode,
            "devices_total": len(self._devices),
            "devices_online": online_devices,
            "pending_operations": pending_ops,
            "cache_size": len(self._local_cache),
            "storage_path": str(self._storage_path),
        }

    def register_sync_handler(self, operation_type: str, handler: Callable):
        """Register a handler for syncing specific operation types."""
        self._sync_handlers[operation_type] = handler
        logger.info(f"Sync handler registered: {operation_type}")

    def get_stats(self) -> Dict[str, Any]:
        """Get edge computing statistics."""
        return {
            "devices": len(self._devices),
            "pending_ops": len(self._pending_ops),
            "sync_queue": len(self._sync_queue),
            "cache_entries": len(self._local_cache),
            "offline_mode": self._offline_mode,
        }


# Global default edge computing engine
default_edge_compute: Optional[EdgeComputingEngine] = None


def init_edge_computing(storage_path: str = "/tmp/edge_storage") -> EdgeComputingEngine:
    """Initialize global edge computing engine."""
    global default_edge_compute
    default_edge_compute = EdgeComputingEngine(storage_path)
    return default_edge_compute
