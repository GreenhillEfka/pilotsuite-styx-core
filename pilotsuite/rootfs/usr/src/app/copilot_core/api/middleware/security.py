"""Security Middleware for API requests.

Provides middleware for:
- Request size limiting
- Security headers
- Request logging
- Suspicious activity detection
"""

from __future__ import annotations

import time
import os
import logging
from typing import Any, Callable, Dict, Optional
from functools import wraps

from flask import request, jsonify, g, make_response

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Security middleware for API requests.
    
    Features:
    - Request size validation (1MB max)
    - Security headers (CSP, X-Frame-Options, etc.)
    - Request timing and logging
    - Suspicious activity detection
    """
    
    def __init__(
        self,
        max_request_size: int = 1024 * 1024,  # 1MB
        enable_security_headers: bool = True,
        enable_request_logging: bool = True,
        log_suspicious_only: bool = False,
    ):
        """Initialize security middleware.
        
        Args:
            max_request_size: Maximum request body size in bytes
            enable_security_headers: Add security headers to responses
            enable_request_logging: Log all requests
            log_suspicious_only: Only log suspicious requests
        """
        self.max_request_size = max_request_size
        self.enable_security_headers = enable_security_headers
        self.enable_request_logging = enable_request_logging
        self.log_suspicious_only = log_suspicious_only
        
        # Suspicious activity thresholds
        self.suspicious_request_size = 512 * 1024  # 512KB
        self.suspicious_param_count = 100
        self.suspicious_header_count = 50
    
    def before_request(self) -> Optional[Any]:
        """Execute before each request.
        
        Returns:
            Response object to abort request, or None to continue
        """
        # Store request start time
        g.request_start_time = time.time()
        
        # Check request size
        content_length = request.content_length
        if content_length and content_length > self.max_request_size:
            from copilot_core.security.security_logs import get_security_logger
            sec_logger = get_security_logger()
            sec_logger.log_request_size_exceeded(
                self._get_client_key(),
                request.path,
                content_length,
            )
            
            logger.warning(
                f"Request size exceeded: {content_length} bytes (max: {self.max_request_size})"
            )
            return jsonify({
                "ok": False,
                "error": "request_too_large",
                "message": f"Request body exceeds maximum size of {self.max_request_size // 1024}KB",
            }), 413
        
        # Check for suspicious activity
        if self._is_suspicious_request():
            from copilot_core.security.security_logs import get_security_logger
            sec_logger = get_security_logger()
            sec_logger.log_suspicious_request(
                self._get_client_key(),
                request.path,
                "Suspicious request pattern detected",
            )
        
        # Log request if enabled
        if self.enable_request_logging and not self.log_suspicious_only:
            self._log_request()
        
        return None
    
    def after_request(self, response) -> Any:
        """Execute after each request.
        
        Args:
            response: Flask response object
            
        Returns:
            Modified response object
        """
        # Add security headers
        if self.enable_security_headers:
            self._add_security_headers(response)
        
        # Add request timing header
        if hasattr(g, "request_start_time"):
            elapsed = time.time() - g.request_start_time
            response.headers["X-Request-Time"] = f"{elapsed:.3f}s"
        
        # Add rate limit headers if available
        if hasattr(g, "rate_limit_info"):
            info = g.rate_limit_info
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        # Log request if enabled (after request)
        if self.enable_request_logging and not self.log_suspicious_only:
            self._log_response(response)
        
        return response
    
    def _add_security_headers(self, response) -> None:
        """Add security headers to response."""
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy (restrictive default)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        
        # Cache control for API responses
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    def _is_suspicious_request(self) -> bool:
        """Check if request appears suspicious.
        
        Returns:
            True if request is suspicious
        """
        # Check request size
        content_length = request.content_length
        if content_length and content_length > self.suspicious_request_size:
            return True
        
        # Check number of query parameters
        if len(request.args) > self.suspicious_param_count:
            return True
        
        # Check number of headers
        if len(request.headers) > self.suspicious_header_count:
            return True
        
        # Check for suspicious patterns in URL
        suspicious_patterns = [
            "..",
            "%2e%2e",
            "<script",
            "javascript:",
            "SELECT",
            "UNION",
            "DROP",
            "EXEC",
        ]
        
        url = request.url.lower()
        for pattern in suspicious_patterns:
            if pattern.lower() in url:
                return True
        
        return False
    
    def _log_request(self) -> None:
        """Log request details."""
        logger.info(
            f"REQUEST {request.method} {request.path} "
            f"from {self._get_client_ip()} "
            f"({request.content_length or 0} bytes)"
        )
    
    def _log_response(self, response) -> None:
        """Log response details."""
        if hasattr(g, "request_start_time"):
            elapsed = time.time() - g.request_start_time
            logger.debug(
                f"RESPONSE {response.status_code} "
                f"in {elapsed:.3f}s"
            )
    
    def _get_client_key(self) -> str:
        """Extract client key from current request."""
        try:
            api_key = request.headers.get("X-API-Key", "").strip()
            if api_key:
                return f"apikey:{api_key[:16]}"
            
            auth_token = request.headers.get("X-Auth-Token", "").strip()
            if auth_token:
                return f"token:{auth_token[:16]}"
            
            auth_header = request.headers.get("Authorization", "").strip()
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                if token:
                    return f"bearer:{token[:16]}"
            
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            return f"ip:{client_ip}"
        except RuntimeError:
            return "unknown"
    
    def _get_client_ip(self) -> str:
        """Extract client IP from request."""
        try:
            return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
        except RuntimeError:
            return "unknown"


# Global middleware instance
_middleware: Optional[SecurityMiddleware] = None


def get_middleware() -> SecurityMiddleware:
    """Get the global security middleware instance."""
    global _middleware
    if _middleware is None:
        max_size = int(os.environ.get("COPILOT_MAX_REQUEST_SIZE", 1024 * 1024))
        enable_headers = os.environ.get("COPILOT_SECURITY_HEADERS", "true").lower() == "true"
        enable_logging = os.environ.get("COPILOT_REQUEST_LOGGING", "true").lower() == "true"
        
        _middleware = SecurityMiddleware(
            max_request_size=max_size,
            enable_security_headers=enable_headers,
            enable_request_logging=enable_logging,
        )
    return _middleware


def init_security_middleware(app) -> None:
    """Initialize security middleware for a Flask app.
    
    Args:
        app: Flask application
    """
    middleware = get_middleware()
    
    app.before_request(middleware.before_request)
    app.after_request(middleware.after_request)
    
    logger.info("Security middleware initialized")


def security_middleware():
    """Decorator to apply security middleware to a blueprint or route.
    
    This is a convenience decorator that applies the middleware's
    before/after request logic to specific routes.
    
    Example:
        @bp.post("/sensitive")
        @security_middleware()
        def sensitive_operation():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            middleware = get_middleware()
            
            # Run before request logic
            result = middleware.before_request()
            if result is not None:
                return result
            
            # Call the actual function
            response = f(*args, **kwargs)
            
            # Run after request logic
            try:
                if not isinstance(response, tuple):
                    response = make_response(response)
                else:
                    response = make_response(response[0], response[1] if len(response) > 1 else 200)
            except RuntimeError:
                # Outside request context
                return response
            
            middleware.after_request(response)
            return response
        
        return decorated_function
    return decorator
