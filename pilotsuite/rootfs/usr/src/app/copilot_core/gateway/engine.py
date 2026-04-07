"""API Gateway & Rate Limiting — Slice 25.

API gateway for PilotSuite Core with rate limiting.

Features:
- Request routing and filtering
- Rate limiting per client/API key
- Request/response logging
- API key management
- Quota enforcement
- Throttling strategies
"""
from __future__ import annotations

import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategy."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class RequestStatus(Enum):
    """Request processing status."""
    ALLOWED = "allowed"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class APIKey:
    """API key for authentication."""
    key_id: str
    key_hash: str  # Hashed key
    name: str
    owner: str
    enabled: bool = True
    rate_limit: int = 100  # Requests per window
    quota_daily: int = 10000  # Daily quota
    quota_used_today: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    last_used: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "name": self.name,
            "owner": self.owner,
            "enabled": self.enabled,
            "rate_limit": self.rate_limit,
            "quota_daily": self.quota_daily,
            "quota_used_today": self.quota_used_today,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used": self.last_used,
        }


@dataclass
class RateLimitState:
    """Rate limit state for a client."""
    client_id: str
    window_start: str
    requests_count: int
    requests_allowed: int
    requests_denied: int
    reset_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "window_start": self.window_start,
            "requests_count": self.requests_count,
            "requests_allowed": self.requests_allowed,
            "requests_denied": self.requests_denied,
            "reset_at": self.reset_at,
        }


@dataclass
class RequestLog:
    """API request log entry."""
    log_id: str
    timestamp: str
    client_id: str
    api_key_id: Optional[str]
    endpoint: str
    method: str
    status: RequestStatus
    response_time_ms: int
    rate_limit_remaining: int
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp,
            "client_id": self.client_id,
            "api_key_id": self.api_key_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "status": self.status.value,
            "response_time_ms": self.response_time_ms,
            "rate_limit_remaining": self.rate_limit_remaining,
            "error_message": self.error_message,
        }


class APIGatewayEngine:
    """API gateway with rate limiting."""
    
    def __init__(self, default_rate_limit: int = 100,
                 default_quota_daily: int = 10000,
                 strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW):
        self._api_keys: Dict[str, APIKey] = {}
        self._rate_limits: Dict[str, RateLimitState] = {}
        self._request_logs: List[RequestLog] = []
        self._log_counter = 0
        
        self._default_rate_limit = default_rate_limit
        self._default_quota_daily = default_quota_daily
        self._strategy = strategy
        self._window_seconds = 60  # 1 minute window
        
        # Middleware chain
        self._middleware: List[Callable] = []
    
    def create_api_key(self, name: str, owner: str,
                      rate_limit: Optional[int] = None,
                      quota_daily: Optional[int] = None,
                      expires_days: Optional[int] = None) -> tuple:
        """Create a new API key."""
        import secrets
        
        # Generate key
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        self._log_counter += 1
        key_id = f"key_{self._log_counter}"
        
        expires_at = None
        if expires_days:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat()
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            owner=owner,
            rate_limit=rate_limit or self._default_rate_limit,
            quota_daily=quota_daily or self._default_quota_daily,
            expires_at=expires_at,
        )
        
        self._api_keys[key_id] = api_key
        
        # Return both key_id and raw_key (raw_key shown only once)
        return key_id, raw_key
    
    def validate_api_key(self, raw_key: str) -> Optional[APIKey]:
        """Validate API key and return key info."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        for api_key in self._api_keys.values():
            if api_key.key_hash == key_hash:
                # Check if enabled
                if not api_key.enabled:
                    return None
                
                # Check expiration
                if api_key.expires_at:
                    expires = datetime.fromisoformat(api_key.expires_at)
                    if expires < datetime.now(timezone.utc):
                        return None
                
                # Update last used
                api_key.last_used = datetime.now(timezone.utc).isoformat()
                
                return api_key
        
        return None
    
    def check_rate_limit(self, client_id: str, api_key: Optional[APIKey] = None) -> tuple:
        """Check if request is within rate limit."""
        now = datetime.now(timezone.utc)
        
        # Get or create rate limit state
        if client_id not in self._rate_limits:
            self._rate_limits[client_id] = self._create_rate_limit_state(client_id, now)
        
        state = self._rate_limits[client_id]
        
        # Check if window has expired
        reset_at = datetime.fromisoformat(state.reset_at)
        if now >= reset_at:
            state = self._create_rate_limit_state(client_id, now)
            self._rate_limits[client_id] = state
        
        # Get limit from API key or default
        limit = api_key.rate_limit if api_key else self._default_rate_limit
        
        # Check rate limit
        if state.requests_count >= limit:
            return RequestStatus.RATE_LIMITED, state
        
        # Check quota
        if api_key and api_key.quota_used_today >= api_key.quota_daily:
            return RequestStatus.QUOTA_EXCEEDED, state
        
        # Allow request
        state.requests_count += 1
        state.requests_allowed += 1
        
        if api_key:
            api_key.quota_used_today += 1
        
        return RequestStatus.ALLOWED, state
    
    def _create_rate_limit_state(self, client_id: str, now: datetime) -> RateLimitState:
        """Create new rate limit state."""
        reset_at = now + timedelta(seconds=self._window_seconds)
        
        return RateLimitState(
            client_id=client_id,
            window_start=now.isoformat(),
            requests_count=0,
            requests_allowed=0,
            requests_denied=0,
            reset_at=reset_at.isoformat(),
        )
    
    def log_request(self, client_id: str, endpoint: str, method: str,
                   status: RequestStatus, response_time_ms: int,
                   api_key_id: Optional[str] = None,
                   rate_limit_remaining: int = 0,
                   error_message: Optional[str] = None) -> str:
        """Log API request."""
        self._log_counter += 1
        
        log = RequestLog(
            log_id=f"log_{self._log_counter}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            status=status,
            response_time_ms=response_time_ms,
            rate_limit_remaining=rate_limit_remaining,
            error_message=error_message,
        )
        
        self._request_logs.append(log)
        
        # Trim logs if too many
        if len(self._request_logs) > 10000:
            self._request_logs = self._request_logs[-10000:]
        
        return log.log_id
    
    def process_request(self, client_id: str, endpoint: str, method: str,
                       raw_key: Optional[str] = None) -> Dict[str, Any]:
        """Process API request through gateway."""
        import time
        start_time = time.time()
        
        # Validate API key if provided
        api_key = None
        if raw_key:
            api_key = self.validate_api_key(raw_key)
            if not api_key:
                self.log_request(client_id, endpoint, method,
                               RequestStatus.BLOCKED, 0,
                               error_message="Invalid API key")
                return {
                    "status": "blocked",
                    "error": "Invalid API key",
                }
        
        # Check rate limit
        status, rate_state = self.check_rate_limit(client_id, api_key)
        
        response_time_ms = int((time.time() - start_time) * 1000)
        rate_remaining = (api_key.rate_limit if api_key else self._default_rate_limit) - rate_state.requests_count
        
        if status != RequestStatus.ALLOWED:
            self.log_request(client_id, endpoint, method, status,
                           response_time_ms, api_key.key_id if api_key else None,
                           rate_remaining, error_message=status.value)
            
            return {
                "status": status.value,
                "error": f"Request {status.value}",
                "retry_after": self._window_seconds,
            }
        
        # Log successful request
        self.log_request(client_id, endpoint, method, status,
                        response_time_ms, api_key.key_id if api_key else None,
                        rate_remaining)
        
        return {
            "status": "allowed",
            "rate_limit_remaining": rate_remaining,
            "quota_remaining": api_key.quota_daily - api_key.quota_used_today if api_key else None,
        }
    
    def get_request_logs(self, client_id: Optional[str] = None,
                        status: Optional[RequestStatus] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """Get request logs."""
        logs = self._request_logs
        
        if client_id:
            logs = [l for l in logs if l.client_id == client_id]
        
        if status:
            logs = [l for l in logs if l.status == status]
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda l: l.timestamp, reverse=True)
        
        return [l.to_dict() for l in logs[:limit]]
    
    def get_api_keys(self, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get API keys."""
        keys = list(self._api_keys.values())
        
        if owner:
            keys = [k for k in keys if k.owner == owner]
        
        return [k.to_dict() for k in keys]
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        if key_id not in self._api_keys:
            return False
        
        self._api_keys[key_id].enabled = False
        return True
    
    def reset_quota(self, key_id: str) -> bool:
        """Reset daily quota for an API key."""
        if key_id not in self._api_keys:
            return False
        
        self._api_keys[key_id].quota_used_today = 0
        return True
    
    def get_rate_limit_status(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get rate limit status for a client."""
        if client_id not in self._rate_limits:
            return None
        
        return self._rate_limits[client_id].to_dict()
    
    def get_gateway_summary(self) -> Dict[str, Any]:
        """Get gateway summary."""
        total_keys = len(self._api_keys)
        active_keys = len([k for k in self._api_keys.values() if k.enabled])
        
        total_requests = len(self._request_logs)
        rate_limited = len([l for l in self._request_logs if l.status == RequestStatus.RATE_LIMITED])
        blocked = len([l for l in self._request_logs if l.status == RequestStatus.BLOCKED])
        
        return {
            "total_api_keys": total_keys,
            "active_api_keys": active_keys,
            "total_requests": total_requests,
            "rate_limited_requests": rate_limited,
            "blocked_requests": blocked,
            "rate_limit_strategy": self._strategy.value,
            "window_seconds": self._window_seconds,
        }
    
    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware to processing chain."""
        self._middleware.append(middleware)
    
    def reset_daily_quotas(self) -> int:
        """Reset all daily quotas (call once per day)."""
        reset_count = 0
        for api_key in self._api_keys.values():
            api_key.quota_used_today = 0
            reset_count += 1
        return reset_count


def create_api_gateway_engine(default_rate_limit: int = 100,
                             default_quota_daily: int = 10000) -> APIGatewayEngine:
    """Factory function to create API gateway engine."""
    return APIGatewayEngine(
        default_rate_limit=default_rate_limit,
        default_quota_daily=default_quota_daily,
    )
