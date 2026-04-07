"""Service Mesh Engine — Slice 46.

Service mesh for PilotSuite Core inter-service communication.

Features:
- Service discovery and registration
- Load balancing (round-robin, least-connections, weighted)
- Circuit breaker pattern
- Retry logic with backoff
- Service health tracking
- Traffic splitting for canary deployments
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class LoadBalanceStrategy(Enum):
    """Load balancing strategy."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    RANDOM = "random"


class CircuitState(Enum):
    """Circuit breaker state."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ServiceInstance:
    """Service instance representation."""
    instance_id: str
    service_name: str
    host: str
    port: int
    weight: int = 100
    status: ServiceStatus = ServiceStatus.UNKNOWN
    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_health_check: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "weight": self.weight,
            "status": self.status.value,
            "active_connections": self.active_connections,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "last_health_check": self.last_health_check,
            "metadata": self.metadata,
            "registered_at": self.registered_at,
        }


@dataclass
class CircuitBreaker:
    """Circuit breaker for service."""
    service_name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: int = 30
    last_failure_at: Optional[str] = None
    last_state_change: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "timeout_seconds": self.timeout_seconds,
            "last_failure_at": self.last_failure_at,
            "last_state_change": self.last_state_change,
        }


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_retries: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 10000
    multiplier: float = 2.0
    retryable_status_codes: List[int] = field(default_factory=lambda: [502, 503, 504])
    
    def get_delay(self, attempt: int) -> int:
        """Calculate delay for attempt using exponential backoff."""
        delay = self.initial_delay_ms * (self.multiplier ** attempt)
        return min(int(delay), self.max_delay_ms)


@dataclass
class TrafficSplit:
    """Traffic split configuration for canary."""
    split_id: str
    service_name: str
    rules: List[Dict[str, Any]]  # [{instance_id, percentage}]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "split_id": self.split_id,
            "service_name": self.service_name,
            "rules": self.rules,
            "created_at": self.created_at,
        }


class ServiceMeshEngine:
    """Service mesh for inter-service communication."""
    
    def __init__(self):
        self._services: Dict[str, List[ServiceInstance]] = {}  # service_name -> [instances]
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._retry_configs: Dict[str, RetryConfig] = {}
        self._traffic_splits: Dict[str, TrafficSplit] = {}
        self._round_robin_index: Dict[str, int] = {}
        
        # Statistics
        self._stats = {
            "total_services": 0,
            "total_instances": 0,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "circuit_breaker_trips": 0,
            "retries": 0,
        }
    
    def register_service(self, service_name: str, host: str, port: int,
                        weight: int = 100,
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """Register a service instance."""
        instance_id = f"svc_{uuid.uuid4().hex[:12]}"
        
        instance = ServiceInstance(
            instance_id=instance_id,
            service_name=service_name,
            host=host,
            port=port,
            weight=weight,
            metadata=metadata or {},
        )
        
        if service_name not in self._services:
            self._services[service_name] = []
            self._circuit_breakers[service_name] = CircuitBreaker(service_name=service_name)
        
        self._services[service_name].append(instance)
        
        self._stats["total_services"] = len(self._services)
        self._stats["total_instances"] += 1
        
        logger.info("Service registered: %s (%s:%d)", service_name, host, port)
        
        return instance_id
    
    def deregister_service(self, instance_id: str) -> bool:
        """Deregister a service instance."""
        for service_name, instances in self._services.items():
            for i, instance in enumerate(instances):
                if instance.instance_id == instance_id:
                    instances.pop(i)
                    self._stats["total_instances"] -= 1
                    
                    if not instances:
                        del self._services[service_name]
                        self._stats["total_services"] = len(self._services)
                    
                    logger.info("Service deregistered: %s", instance_id)
                    return True
        
        return False
    
    def get_healthy_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get healthy instances for a service."""
        if service_name not in self._services:
            return []
        
        return [
            inst for inst in self._services[service_name]
            if inst.status in (ServiceStatus.HEALTHY, ServiceStatus.UNKNOWN)
        ]
    
    def select_instance(self, service_name: str,
                       strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN) -> Optional[ServiceInstance]:
        """Select an instance using load balancing strategy."""
        instances = self.get_healthy_instances(service_name)
        
        if not instances:
            return None
        
        # Check circuit breaker
        if not self._can_request(service_name):
            logger.warning("Circuit breaker open for %s", service_name)
            return None
        
        if strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._select_round_robin(service_name, instances)
        elif strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return self._select_least_connections(instances)
        elif strategy == LoadBalanceStrategy.WEIGHTED:
            return self._select_weighted(instances)
        elif strategy == LoadBalanceStrategy.RANDOM:
            return random.choice(instances)
        
        return instances[0]
    
    def _select_round_robin(self, service_name: str,
                           instances: List[ServiceInstance]) -> ServiceInstance:
        """Select instance using round-robin."""
        if service_name not in self._round_robin_index:
            self._round_robin_index[service_name] = 0
        
        index = self._round_robin_index[service_name]
        instance = instances[index % len(instances)]
        self._round_robin_index[service_name] = (index + 1) % len(instances)
        
        return instance
    
    def _select_least_connections(self,
                                 instances: List[ServiceInstance]) -> ServiceInstance:
        """Select instance with least active connections."""
        return min(instances, key=lambda i: i.active_connections)
    
    def _select_weighted(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Select instance using weighted random."""
        total_weight = sum(i.weight for i in instances)
        r = random.randint(1, total_weight)
        
        cumulative = 0
        for instance in instances:
            cumulative += instance.weight
            if r <= cumulative:
                return instance
        
        return instances[-1]
    
    def _can_request(self, service_name: str) -> bool:
        """Check if circuit breaker allows request."""
        if service_name not in self._circuit_breakers:
            return True
        
        cb = self._circuit_breakers[service_name]
        
        if cb.state == CircuitState.CLOSED:
            return True
        
        if cb.state == CircuitState.OPEN:
            # Check if timeout has passed
            if cb.last_failure_at:
                last_failure = datetime.fromisoformat(cb.last_failure_at)
                elapsed = (datetime.now(timezone.utc) - last_failure).total_seconds()
                
                if elapsed >= cb.timeout_seconds:
                    cb.state = CircuitState.HALF_OPEN
                    cb.last_state_change = datetime.now(timezone.utc).isoformat()
                    return True
            
            return False
        
        # HALF_OPEN - allow one request to test
        return True
    
    def record_success(self, service_name: str, instance_id: str) -> None:
        """Record successful request."""
        self._stats["total_requests"] += 1
        self._stats["successful_requests"] += 1
        
        # Update instance stats
        self._update_instance_stats(service_name, instance_id, success=True)
        
        # Update circuit breaker
        self._record_circuit_success(service_name)
    
    def record_failure(self, service_name: str, instance_id: str,
                      status_code: Optional[int] = None) -> None:
        """Record failed request."""
        self._stats["total_requests"] += 1
        self._stats["failed_requests"] += 1
        
        # Update instance stats
        self._update_instance_stats(service_name, instance_id, success=False)
        
        # Update circuit breaker
        self._record_circuit_failure(service_name)
    
    def _update_instance_stats(self, service_name: str, instance_id: str,
                              success: bool) -> None:
        """Update instance statistics."""
        if service_name not in self._services:
            return
        
        for instance in self._services[service_name]:
            if instance.instance_id == instance_id:
                instance.total_requests += 1
                if not success:
                    instance.failed_requests += 1
                break
    
    def _record_circuit_success(self, service_name: str) -> None:
        """Record success in circuit breaker."""
        if service_name not in self._circuit_breakers:
            return
        
        cb = self._circuit_breakers[service_name]
        
        if cb.state == CircuitState.HALF_OPEN:
            cb.success_count += 1
            
            if cb.success_count >= cb.success_threshold:
                cb.state = CircuitState.CLOSED
                cb.failure_count = 0
                cb.success_count = 0
                cb.last_state_change = datetime.now(timezone.utc).isoformat()
                logger.info("Circuit breaker closed for %s", service_name)
        
        elif cb.state == CircuitState.CLOSED:
            # Reset failure count on success
            cb.failure_count = 0
    
    def _record_circuit_failure(self, service_name: str) -> None:
        """Record failure in circuit breaker."""
        if service_name not in self._circuit_breakers:
            return
        
        cb = self._circuit_breakers[service_name]
        cb.failure_count += 1
        cb.last_failure_at = datetime.now(timezone.utc).isoformat()
        
        if cb.state == CircuitState.HALF_OPEN:
            cb.state = CircuitState.OPEN
            cb.last_state_change = datetime.now(timezone.utc).isoformat()
            self._stats["circuit_breaker_trips"] += 1
            logger.warning("Circuit breaker opened for %s", service_name)
        
        elif cb.state == CircuitState.CLOSED:
            if cb.failure_count >= cb.failure_threshold:
                cb.state = CircuitState.OPEN
                cb.last_state_change = datetime.now(timezone.utc).isoformat()
                self._stats["circuit_breaker_trips"] += 1
                logger.warning("Circuit breaker tripped for %s", service_name)
    
    def configure_circuit_breaker(self, service_name: str,
                                 failure_threshold: int = 5,
                                 success_threshold: int = 3,
                                 timeout_seconds: int = 30) -> bool:
        """Configure circuit breaker for service."""
        if service_name not in self._circuit_breakers:
            return False
        
        cb = self._circuit_breakers[service_name]
        cb.failure_threshold = failure_threshold
        cb.success_threshold = success_threshold
        cb.timeout_seconds = timeout_seconds
        
        return True
    
    def configure_retry(self, service_name: str,
                       max_retries: int = 3,
                       initial_delay_ms: int = 100,
                       max_delay_ms: int = 10000,
                       multiplier: float = 2.0) -> RetryConfig:
        """Configure retry logic for service."""
        config = RetryConfig(
            max_retries=max_retries,
            initial_delay_ms=initial_delay_ms,
            max_delay_ms=max_delay_ms,
            multiplier=multiplier,
        )
        
        self._retry_configs[service_name] = config
        
        return config
    
    def get_retry_config(self, service_name: str) -> Optional[RetryConfig]:
        """Get retry config for service."""
        return self._retry_configs.get(service_name)
    
    def create_traffic_split(self, service_name: str,
                            rules: List[Dict[str, Any]]) -> str:
        """Create traffic split for canary deployment."""
        split_id = f"split_{uuid.uuid4().hex[:8]}"
        
        split = TrafficSplit(
            split_id=split_id,
            service_name=service_name,
            rules=rules,
        )
        
        self._traffic_splits[split_id] = split
        
        logger.info("Traffic split created: %s for %s", split_id, service_name)
        
        return split_id
    
    def select_instance_with_traffic_split(self, split_id: str) -> Optional[ServiceInstance]:
        """Select instance based on traffic split rules."""
        if split_id not in self._traffic_splits:
            return None
        
        split = self._traffic_splits[split_id]
        
        # Weighted random based on split rules
        r = random.randint(1, 100)
        cumulative = 0
        
        for rule in split.rules:
            cumulative += rule.get("percentage", 0)
            if r <= cumulative:
                instance_id = rule.get("instance_id")
                
                # Find the instance
                if split.service_name in self._services:
                    for instance in self._services[split.service_name]:
                        if instance.instance_id == instance_id:
                            return instance
        
        return None
    
    def update_instance_health(self, instance_id: str,
                              status: ServiceStatus) -> bool:
        """Update instance health status."""
        for instances in self._services.values():
            for instance in instances:
                if instance.instance_id == instance_id:
                    instance.status = status
                    instance.last_health_check = datetime.now(timezone.utc).isoformat()
                    return True
        
        return False
    
    def get_service(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service info with instances."""
        if service_name not in self._services:
            return None
        
        instances = self._services[service_name]
        cb = self._circuit_breakers.get(service_name)
        
        return {
            "service_name": service_name,
            "instance_count": len(instances),
            "instances": [i.to_dict() for i in instances],
            "circuit_breaker": cb.to_dict() if cb else None,
        }
    
    def get_all_services(self) -> List[Dict[str, Any]]:
        """Get all services."""
        return [
            {
                "service_name": name,
                "instance_count": len(instances),
                "healthy_count": len([i for i in instances if i.status in (ServiceStatus.HEALTHY, ServiceStatus.UNKNOWN)]),
            }
            for name, instances in self._services.items()
        ]
    
    def get_circuit_breaker(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker state."""
        if service_name not in self._circuit_breakers:
            return None
        
        return self._circuit_breakers[service_name].to_dict()
    
    def reset_circuit_breaker(self, service_name: str) -> bool:
        """Reset circuit breaker to closed state."""
        if service_name not in self._circuit_breakers:
            return False
        
        cb = self._circuit_breakers[service_name]
        cb.state = CircuitState.CLOSED
        cb.failure_count = 0
        cb.success_count = 0
        cb.last_state_change = datetime.now(timezone.utc).isoformat()
        
        logger.info("Circuit breaker reset for %s", service_name)
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service mesh statistics."""
        return {
            **self._stats,
            "circuit_breakers": len(self._circuit_breakers),
            "traffic_splits": len(self._traffic_splits),
        }


def create_service_mesh_engine() -> ServiceMeshEngine:
    """Factory function to create service mesh engine."""
    return ServiceMeshEngine()
