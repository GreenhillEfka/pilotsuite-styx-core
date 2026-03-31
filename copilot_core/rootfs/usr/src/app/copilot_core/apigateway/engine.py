"""API Gateway Engine — Slice 45.

API Gateway for PilotSuite Core HTTP routing and management.

Features:
- Route registration and matching
- Request/response middleware
- Rate limiting integration
- Authentication hooks
- Request transformation
- Response caching
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class HTTPMethod(Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class RouteStatus(Enum):
    """Route status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


@dataclass
class RouteConfig:
    """Route configuration."""
    route_id: str
    path: str
    method: HTTPMethod
    handler: Callable
    status: RouteStatus = RouteStatus.ACTIVE
    auth_required: bool = False
    rate_limit_id: Optional[str] = None
    middleware: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    cache_ttl_seconds: int = 0
    tags: List[str] = field(default_factory=list)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "path": self.path,
            "method": self.method.value,
            "status": self.status.value,
            "auth_required": self.auth_required,
            "rate_limit_id": self.rate_limit_id,
            "middleware": self.middleware,
            "timeout_seconds": self.timeout_seconds,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "tags": self.tags,
            "description": self.description,
        }


@dataclass
class Request:
    """HTTP request representation."""
    request_id: str
    method: HTTPMethod
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[Dict[str, Any]] = None
    path_params: Dict[str, str] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "method": self.method.value,
            "path": self.path,
            "headers": self.headers,
            "query_params": self.query_params,
            "body": self.body,
            "path_params": self.path_params,
            "context": self.context,
            "created_at": self.created_at,
        }


@dataclass
class Response:
    """HTTP response representation."""
    status_code: int
    body: Any
    headers: Dict[str, str] = field(default_factory=dict)
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status_code": self.status_code,
            "body": self.body,
            "headers": self.headers,
            "cached": self.cached,
        }
    
    @classmethod
    def ok(cls, body: Any, headers: Optional[Dict[str, str]] = None) -> Response:
        return cls(status_code=200, body=body, headers=headers or {})
    
    @classmethod
    def created(cls, body: Any, headers: Optional[Dict[str, str]] = None) -> Response:
        hdr = headers or {}
        return cls(status_code=201, body=body, headers=hdr)
    
    @classmethod
    def bad_request(cls, message: str) -> Response:
        return cls(status_code=400, body={"error": message})
    
    @classmethod
    def unauthorized(cls, message: str = "Unauthorized") -> Response:
        return cls(status_code=401, body={"error": message})
    
    @classmethod
    def forbidden(cls, message: str = "Forbidden") -> Response:
        return cls(status_code=403, body={"error": message})
    
    @classmethod
    def not_found(cls, message: str = "Not Found") -> Response:
        return cls(status_code=404, body={"error": message})
    
    @classmethod
    def internal_error(cls, message: str = "Internal Server Error") -> Response:
        return cls(status_code=500, body={"error": message})


@dataclass
class MiddlewareRegistration:
    """Registered middleware."""
    middleware_id: str
    name: str
    handler: Callable[[Request, Callable], Response]
    priority: int = 0
    routes: List[str] = field(default_factory=list)  # Empty = all routes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "middleware_id": self.middleware_id,
            "name": self.name,
            "priority": self.priority,
            "routes": self.routes,
        }


class APIGatewayEngine:
    """API Gateway routing and management engine."""
    
    def __init__(self):
        self._routes: Dict[str, RouteConfig] = {}
        self._middleware: Dict[str, MiddlewareRegistration] = {}
        self._cache: Dict[str, Tuple[Response, str]] = {}  # cache_key -> (response, expires_at)
        self._auth_handlers: Dict[str, Callable[[Request], bool]] = {}
        
        # Request statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cached_responses": 0,
            "by_route": {},
            "by_method": {},
            "by_status_code": {},
        }
    
    def register_route(self, path: str, method: str,
                      handler: Callable[[Request], Response],
                      route_id: Optional[str] = None,
                      auth_required: bool = False,
                      rate_limit_id: Optional[str] = None,
                      middleware: Optional[List[str]] = None,
                      timeout_seconds: int = 30,
                      cache_ttl_seconds: int = 0,
                      tags: Optional[List[str]] = None,
                      description: str = "") -> str:
        """Register a route."""
        if route_id is None:
            route_id = f"route_{uuid.uuid4().hex[:8]}"
        
        route = RouteConfig(
            route_id=route_id,
            path=path,
            method=HTTPMethod(method.upper()),
            handler=handler,
            auth_required=auth_required,
            rate_limit_id=rate_limit_id,
            middleware=middleware or [],
            timeout_seconds=timeout_seconds,
            cache_ttl_seconds=cache_ttl_seconds,
            tags=tags or [],
            description=description,
        )
        
        self._routes[route_id] = route
        
        logger.info("Route registered: %s %s (%s)", method.upper(), path, route_id)
        
        return route_id
    
    def register_middleware(self, name: str,
                           handler: Callable[[Request, Callable], Response],
                           middleware_id: Optional[str] = None,
                           priority: int = 0,
                           routes: Optional[List[str]] = None) -> str:
        """Register middleware."""
        if middleware_id is None:
            middleware_id = f"mw_{uuid.uuid4().hex[:8]}"
        
        mw = MiddlewareRegistration(
            middleware_id=middleware_id,
            name=name,
            handler=handler,
            priority=priority,
            routes=routes or [],
        )
        
        self._middleware[middleware_id] = mw
        
        logger.info("Middleware registered: %s (%s)", name, middleware_id)
        
        return middleware_id
    
    def register_auth_handler(self, auth_type: str,
                             handler: Callable[[Request], bool]) -> None:
        """Register authentication handler."""
        self._auth_handlers[auth_type] = handler
        logger.info("Auth handler registered: %s", auth_type)
    
    def handle_request(self, method: str, path: str,
                      headers: Optional[Dict[str, str]] = None,
                      query_params: Optional[Dict[str, str]] = None,
                      body: Optional[Dict[str, Any]] = None) -> Response:
        """Handle an incoming request."""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        request = Request(
            request_id=request_id,
            method=HTTPMethod(method.upper()),
            path=path,
            headers=headers or {},
            query_params=query_params or {},
            body=body,
        )
        
        self._stats["total_requests"] += 1
        
        # Find matching route
        route, path_params = self._match_route(request.method, request.path)
        
        if not route:
            self._stats["failed_requests"] += 1
            return Response.not_found(f"No route found for {method} {path}")
        
        if route.status != RouteStatus.ACTIVE:
            self._stats["failed_requests"] += 1
            return Response.internal_error("Route unavailable")
        
        # Update stats
        self._stats["by_route"][route.route_id] = self._stats["by_route"].get(route.route_id, 0) + 1
        self._stats["by_method"][method.upper()] = self._stats["by_method"].get(method.upper(), 0) + 1
        
        # Add path params to request
        request.path_params = path_params
        
        # Check cache
        if route.cache_ttl_seconds > 0 and method == "GET":
            cache_key = f"{method}:{path}"
            if cache_key in self._cache:
                response, expires_at = self._cache[cache_key]
                if datetime.fromisoformat(expires_at) > datetime.now(timezone.utc):
                    response.cached = True
                    self._stats["cached_responses"] += 1
                    self._stats["successful_requests"] += 1
                    return response
        
        # Check authentication
        if route.auth_required:
            auth_response = self._authenticate(request)
            if auth_response:
                self._stats["failed_requests"] += 1
                return auth_response
        
        # Build middleware chain
        middleware_chain = self._build_middleware_chain(route)
        
        # Execute request through middleware chain
        try:
            response = self._execute_middleware_chain(request, route, middleware_chain)
            
            # Cache response if applicable
            if route.cache_ttl_seconds > 0 and method == "GET" and response.status_code == 200:
                cache_key = f"{method}:{path}"
                expires_at = (datetime.now(timezone.utc) + timedelta(seconds=route.cache_ttl_seconds)).isoformat()
                self._cache[cache_key] = (response, expires_at)
            
            # Update stats
            if 200 <= response.status_code < 400:
                self._stats["successful_requests"] += 1
            else:
                self._stats["failed_requests"] += 1
            
            self._stats["by_status_code"][str(response.status_code)] = \
                self._stats["by_status_code"].get(str(response.status_code), 0) + 1
            
            return response
            
        except Exception as exc:
            logger.exception("Request handling failed: %s", exc)
            self._stats["failed_requests"] += 1
            return Response.internal_error(str(exc))
    
    def _match_route(self, method: HTTPMethod, path: str) -> Tuple[Optional[RouteConfig], Dict[str, str]]:
        """Match request to route."""
        path_params = {}
        
        for route in self._routes.values():
            if route.method != method:
                continue
            
            # Exact match
            if route.path == path:
                return route, {}
            
            # Parameterized match (e.g., /users/:id)
            if ":" in route.path:
                pattern = re.sub(r":(\w+)", r"(?P<\1>[^/]+)", route.path)
                match = re.match(f"^{pattern}$", path)
                
                if match:
                    path_params = match.groupdict()
                    return route, path_params
        
        return None, {}
    
    def _authenticate(self, request: Request) -> Optional[Response]:
        """Authenticate request."""
        # Check for auth header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header:
            return Response.unauthorized("Missing authorization header")
        
        # Try registered auth handlers
        for auth_type, handler in self._auth_handlers.items():
            if auth_type.lower() in auth_header.lower():
                try:
                    if handler(request):
                        return None
                    else:
                        return Response.unauthorized("Authentication failed")
                except Exception as exc:
                    logger.exception("Auth handler failed: %s", exc)
                    return Response.internal_error("Authentication error")
        
        # Default: accept if header present
        return None
    
    def _build_middleware_chain(self, route: RouteConfig) -> List[MiddlewareRegistration]:
        """Build middleware chain for route."""
        chain = []
        
        # Add global middleware (no routes specified)
        for mw in self._middleware.values():
            if not mw.routes:
                chain.append(mw)
        
        # Add route-specific middleware
        for mw_id in route.middleware:
            if mw_id in self._middleware:
                chain.append(self._middleware[mw_id])
        
        # Sort by priority (higher first)
        chain.sort(key=lambda m: m.priority, reverse=True)
        
        return chain
    
    def _execute_middleware_chain(self, request: Request,
                                 route: RouteConfig,
                                 middleware_chain: List[MiddlewareRegistration]) -> Response:
        """Execute middleware chain and handler."""
        index = 0
        
        def next_middleware(req: Request) -> Response:
            nonlocal index
            
            if index < len(middleware_chain):
                mw = middleware_chain[index]
                index += 1
                return mw.handler(req, next_middleware)
            else:
                # All middleware done, call handler
                return route.handler(req)
        
        return next_middleware(request)
    
    def get_route(self, route_id: str) -> Optional[Dict[str, Any]]:
        """Get route configuration."""
        if route_id not in self._routes:
            return None
        
        return self._routes[route_id].to_dict()
    
    def get_all_routes(self, status: Optional[RouteStatus] = None,
                      method: Optional[str] = None,
                      tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all routes with optional filters."""
        routes = list(self._routes.values())
        
        if status:
            routes = [r for r in routes if r.status == status]
        
        if method:
            routes = [r for r in routes if r.method.value == method.upper()]
        
        if tag:
            routes = [r for r in routes if tag in r.tags]
        
        return [r.to_dict() for r in routes]
    
    def enable_route(self, route_id: str) -> bool:
        """Enable a route."""
        if route_id not in self._routes:
            return False
        
        self._routes[route_id].status = RouteStatus.ACTIVE
        return True
    
    def disable_route(self, route_id: str) -> bool:
        """Disable a route."""
        if route_id not in self._routes:
            return False
        
        self._routes[route_id].status = RouteStatus.INACTIVE
        return True
    
    def deprecate_route(self, route_id: str) -> bool:
        """Deprecate a route."""
        if route_id not in self._routes:
            return False
        
        self._routes[route_id].status = RouteStatus.DEPRECATED
        return True
    
    def delete_route(self, route_id: str) -> bool:
        """Delete a route."""
        if route_id not in self._routes:
            return False
        
        del self._routes[route_id]
        
        # Clear related cache
        keys_to_remove = [k for k in self._cache if k.startswith(f"GET:")]
        for key in keys_to_remove:
            del self._cache[key]
        
        return True
    
    def get_middleware(self, middleware_id: str) -> Optional[Dict[str, Any]]:
        """Get middleware configuration."""
        if middleware_id not in self._middleware:
            return None
        
        return self._middleware[middleware_id].to_dict()
    
    def get_all_middleware(self) -> List[Dict[str, Any]]:
        """Get all middleware."""
        return [mw.to_dict() for mw in self._middleware.values()]
    
    def clear_cache(self, pattern: Optional[str] = None) -> int:
        """Clear response cache."""
        if pattern:
            keys_to_remove = [k for k in self._cache if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)
        else:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get gateway statistics."""
        cache_size = len(self._cache)
        
        return {
            **self._stats,
            "cache_size": cache_size,
            "total_routes": len(self._routes),
            "total_middleware": len(self._middleware),
            "cache_hit_rate": round(self._stats["cached_responses"] / max(1, self._stats["total_requests"]), 4),
        }
    
    def get_cached_keys(self) -> List[str]:
        """Get all cache keys."""
        return list(self._cache.keys())
    
    def invalidate_cache_for_path(self, path: str) -> int:
        """Invalidate cache for specific path."""
        keys_to_remove = [k for k in self._cache if k.endswith(f":{path}")]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)


# Import timedelta for cache expiry
from datetime import timedelta


def create_api_gateway_engine() -> APIGatewayEngine:
    """Factory function to create API gateway engine."""
    return APIGatewayEngine()
