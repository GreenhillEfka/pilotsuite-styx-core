"""API Gateway v2 — Enhanced routing, load balancing, circuit breaker."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import time

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    IP_HASH = "ip_hash"
    WEIGHTED = "weighted"


@dataclass
class UpstreamServer:
    id: str
    url: str
    weight: int = 1
    active_connections: int = 0
    healthy: bool = True
    last_health_check: float = 0.0


@dataclass
class CircuitBreakerState:
    failures: int = 0
    last_failure: float = 0.0
    state: str = "closed"  # closed, open, half_open
    recovery_timeout: float = 30.0


class APIGatewayV2:
    """Enhanced API gateway with advanced routing and resilience."""

    def __init__(self):
        self._upstreams: Dict[str, List[UpstreamServer]] = {}
        self._routes: List[Dict] = []
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._balancer_strategy = LoadBalancingStrategy.ROUND_ROBIN

    def add_upstream(self, service: str, server: UpstreamServer):
        """Add an upstream server."""
        if service not in self._upstreams:
            self._upstreams[service] = []
        self._upstreams[service].append(server)
        logger.info(f"Upstream added: {service} -> {server.url}")

    def add_route(self, path_pattern: str, service: str, methods: List[str] = None):
        """Add a routing rule."""
        self._routes.append({
            "path": path_pattern,
            "service": service,
            "methods": methods or ["GET", "POST", "PUT", "DELETE"],
        })

    def route_request(self, path: str, method: str = "GET") -> Optional[str]:
        """Route a request to appropriate upstream."""
        # Find matching route
        for route in self._routes:
            if path.startswith(route["path"]) and method in route["methods"]:
                service = route["service"]
                if service in self._upstreams:
                    return self._select_upstream(service)
        return None

    def _select_upstream(self, service: str) -> Optional[str]:
        """Select upstream using load balancing."""
        servers = [s for s in self._upstreams.get(service, []) if s.healthy]
        if not servers:
            return None

        if self._balancer_strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return servers[int(time.time()) % len(servers)].url
        elif self._balancer_strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return min(servers, key=lambda s: s.active_connections).url
        return servers[0].url

    def check_circuit_breaker(self, service: str) -> bool:
        """Check circuit breaker status."""
        cb = self._circuit_breakers.get(service, CircuitBreakerState())
        if cb.state == "open":
            if time.time() - cb.last_failure > cb.recovery_timeout:
                cb.state = "half_open"
                return True
            return False
        return True

    def record_failure(self, service: str):
        """Record upstream failure."""
        if service not in self._circuit_breakers:
            self._circuit_breakers[service] = CircuitBreakerState()
        cb = self._circuit_breakers[service]
        cb.failures += 1
        cb.last_failure = time.time()
        if cb.failures >= 5:
            cb.state = "open"

    def record_success(self, service: str):
        """Record upstream success."""
        if service in self._circuit_breakers:
            cb = self._circuit_breakers[service]
            cb.failures = 0
            cb.state = "closed"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "upstreams": len(self._upstreams),
            "routes": len(self._routes),
            "circuit_breakers": len(self._circuit_breakers),
        }


# Global default gateway v2
default_gateway_v2: Optional[APIGatewayV2] = None


def init_gateway_v2() -> APIGatewayV2:
    global default_gateway_v2
    default_gateway_v2 = APIGatewayV2()
    return default_gateway_v2
