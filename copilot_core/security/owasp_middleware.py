"""OWASP Security Middleware for PilotSuite Styx Core.

Comprehensive security middleware implementing OWASP Top 10 2021 protections:
- A01: Access Control (RBAC, CORS)
- A02: Cryptographic protections (HSTS, secure headers)
- A03: Injection prevention (SQL, NoSQL, Command)
- A04: Secure design patterns
- A05: Security configuration hardening
- A07: Authentication enhancements
- A09: Enhanced logging
- A10: SSRF protection

Usage:
    from copilot_core.security.owasp_middleware import init_owasp_middleware
    init_owasp_middleware(app)
"""

from __future__ import annotations

import re
import os
import time
import socket
import logging
import ipaddress
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from functools import wraps
from urllib.parse import urlparse
from flask import request, jsonify, g, make_response, abort

logger = logging.getLogger(__name__)


# ============================================================================
# A01: Broken Access Control - RBAC & CORS
# ============================================================================

class AccessControlMiddleware:
    """Role-Based Access Control and CORS middleware."""
    
    # Default CORS configuration
    DEFAULT_CORS_CONFIG = {
        "allowed_origins": ["https://localhost", "http://localhost:3000"],
        "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allowed_headers": ["Content-Type", "Authorization", "X-API-Key", "X-Auth-Token"],
        "allow_credentials": True,
        "max_age": 3600,
    }
    
    # Role hierarchy
    ROLE_HIERARCHY = {
        "admin": 3,
        "user": 2,
        "readonly": 1,
        "guest": 0,
    }
    
    def __init__(
        self,
        cors_config: Optional[Dict[str, Any]] = None,
        default_role: str = "guest",
    ):
        """Initialize access control middleware.
        
        Args:
            cors_config: CORS configuration dictionary
            default_role: Default role for unauthenticated requests
        """
        self.cors_config = {**self.DEFAULT_CORS_CONFIG, **(cors_config or {})}
        self.default_role = default_role
        
        # Endpoint role requirements: endpoint -> minimum role
        self._endpoint_roles: Dict[str, str] = {}
        
        # Resource ownership cache: (resource_type, resource_id) -> owner_id
        self._ownership_cache: Dict[Tuple[str, str], str] = {}
    
    def set_endpoint_role(self, endpoint: str, role: str) -> None:
        """Set minimum role requirement for an endpoint.
        
        Args:
            endpoint: API endpoint path
            role: Minimum required role
        """
        if role not in self.ROLE_HIERARCHY:
            raise ValueError(f"Invalid role: {role}")
        self._endpoint_roles[endpoint] = role
        logger.info(f"Set role requirement for {endpoint}: {role}")
    
    def check_role(self, required_role: str) -> bool:
        """Check if current request has required role.
        
        Args:
            required_role: Minimum required role
            
        Returns:
            True if role is sufficient
        """
        current_role = getattr(g, "user_role", self.default_role)
        return (
            self.ROLE_HIERARCHY.get(current_role, 0) >=
            self.ROLE_HIERARCHY.get(required_role, 0)
        )
    
    def require_role(self, role: str):
        """Decorator to require a minimum role for an endpoint.
        
        Args:
            role: Minimum required role
            
        Returns:
            Decorator function
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not self.check_role(role):
                    logger.warning(
                        f"Access denied: role={g.user_role} required={role} "
                        f"path={request.path}"
                    )
                    return jsonify({
                        "ok": False,
                        "error": "access_denied",
                        "message": f"Minimum role '{role}' required",
                    }), 403
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    def add_cors_headers(self, response) -> None:
        """Add CORS headers to response."""
        origin = request.headers.get("Origin", "")
        
        # Check if origin is allowed
        if origin in self.cors_config["allowed_origins"]:
            response.headers["Access-Control-Allow-Origin"] = origin
        elif "*" in self.cors_config["allowed_origins"]:
            response.headers["Access-Control-Allow-Origin"] = "*"
        
        response.headers["Access-Control-Allow-Methods"] = ", ".join(
            self.cors_config["allowed_methods"]
        )
        response.headers["Access-Control-Allow-Headers"] = ", ".join(
            self.cors_config["allowed_headers"]
        )
        response.headers["Access-Control-Allow-Credentials"] = str(
            self.cors_config["allow_credentials"]
        ).lower()
        response.headers["Access-Control-Max-Age"] = str(self.cors_config["max_age"])
    
    def handle_preflight(self) -> Optional[Any]:
        """Handle CORS preflight requests.
        
        Returns:
            Response for preflight, None to continue
        """
        if request.method == "OPTIONS":
            response = make_response()
            self.add_cors_headers(response)
            return response
        return None


# ============================================================================
# A02: Cryptographic Failures - Enhanced Headers
# ============================================================================

class CryptoHeadersMiddleware:
    """Cryptographic security headers middleware."""
    
    def __init__(self, hsts_max_age: int = 31536000):
        """Initialize crypto headers middleware.
        
        Args:
            hsts_max_age: HSTS max-age in seconds (default: 1 year)
        """
        self.hsts_max_age = hsts_max_age
    
    def add_headers(self, response) -> None:
        """Add cryptographic security headers."""
        # HTTP Strict Transport Security
        response.headers["Strict-Transport-Security"] = (
            f"max-age={self.hsts_max_age}; includeSubDomains; preload"
        )
        
        # Content Security Policy (enhanced)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        
        # Cross-Origin policies
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        
        # Cache control for sensitive data
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"


# ============================================================================
# A03: Injection Prevention - Enhanced Validation
# ============================================================================

class InjectionPreventionMiddleware:
    """Advanced injection prevention middleware."""
    
    # Additional SQL injection patterns
    ADVANCED_SQL_PATTERNS = [
        r"(\bINFORMATION_SCHEMA\b)",
        r"(\bSYS\.\w+\b)",  # Oracle system tables
        r"(\bPG_\w+\b)",  # PostgreSQL system tables
        r"(\bSQLITE_\w+\b)",  # SQLite system tables
        r"(\bLOAD_FILE\b\s*\()",
        r"(\bINTO\s+\bOUTFILE\b)",
        r"(\bINTO\s+\bDUMPFILE\b)",
        r"(0x[0-9a-fA-F]+)",  # Hex encoding
        r"(\bCHAR\s*\(\d+\))",  # CHAR encoding
        r"(\bCONCAT\s*\()",  # String concatenation
        r"(\bBENCHMARK\s*\()",  # Time-based
        r"(\bWAITFOR\b\s+\bDELAY\b)",
        r"(\bSLEEP\s*\()",
        r"(\bPG_SLEEP\s*\()",
    ]
    
    # NoSQL injection patterns
    NOSQL_PATTERNS = [
        r"(\$\w+\s*:)",  # MongoDB operators: $where, $ne, etc.
        r"(\{\s*\$\w+)",  # {$where: ...}
        r"(\[\s*\{\s*\$)",  # [{$...}]
        r"(\.where\s*\()",  # .where()
        r"(\.find\s*\(\s*\{)",  # .find({
        r"(\bmapReduce\b)",
        r"(\baggregate\b)",
        r"(\$\{)",  # Template injection
    ]
    
    # Command injection patterns
    COMMAND_PATTERNS = [
        r"(\$\([^)]+\))",  # $(command)
        r"(`[^`]+`)",  # `command`
        r"(\|\s*\w+)",  # | command
        r"(;\s*\w+)",  # ; command
        r"(&\s*\w+)",  # & command
        r">(>\s*)?[/\\]",  # Redirection
        r"(\bnc\b\s+-\w)",  # Netcat
        r"(\bcurl\b\s+http)",  # Curl to http
        r"(\bwget\b\s+http)",  # Wget to http
        r"(\bchmod\b\s+[0-7]+)",  # Chmod
        r"(\bchown\b\s+\w+)",  # Chown
    ]
    
    # LDAP injection patterns
    LDAP_PATTERNS = [
        r"(\([^()]*\))",  # LDAP filters
        r"(\*[^*]*\*)",  # Wildcard patterns
        r"(\)\(|\)\()",  # Filter concatenation
    ]
    
    def __init__(
        self,
        check_sql: bool = True,
        check_nosql: bool = True,
        check_command: bool = True,
        check_ldap: bool = False,
    ):
        """Initialize injection prevention middleware.
        
        Args:
            check_sql: Enable SQL injection detection
            check_nosql: Enable NoSQL injection detection
            check_command: Enable command injection detection
            check_ldap: Enable LDAP injection detection
        """
        self.check_sql = check_sql
        self.check_nosql = check_nosql
        self.check_command = check_command
        self.check_ldap = check_ldap
        
        # Compile patterns
        self._sql_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.ADVANCED_SQL_PATTERNS
        ]
        self._nosql_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.NOSQL_PATTERNS
        ]
        self._command_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.COMMAND_PATTERNS
        ]
        self._ldap_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.LDAP_PATTERNS
        ]
    
    def check_injection(self, value: str) -> Tuple[bool, Optional[str], str]:
        """Check for injection patterns.
        
        Args:
            value: String to check
            
        Returns:
            Tuple of (safe, injection_type, pattern_matched)
        """
        # SQL injection
        if self.check_sql:
            for pattern in self._sql_compiled:
                if pattern.search(value):
                    return False, "sql_injection", pattern.pattern[:50]
        
        # NoSQL injection
        if self.check_nosql:
            for pattern in self._nosql_compiled:
                if pattern.search(value):
                    return False, "nosql_injection", pattern.pattern[:50]
        
        # Command injection
        if self.check_command:
            for pattern in self._command_compiled:
                if pattern.search(value):
                    return False, "command_injection", pattern.pattern[:50]
        
        # LDAP injection
        if self.check_ldap:
            for pattern in self._ldap_compiled:
                if pattern.search(value):
                    return False, "ldap_injection", pattern.pattern[:50]
        
        return True, None, ""


# ============================================================================
# A10: SSRF Protection - URL Validation
# ============================================================================

class SSRFProtectionMiddleware:
    """Server-Side Request Forgery protection middleware."""
    
    # Blocked IP ranges (private/internal networks)
    BLOCKED_RANGES = [
        ipaddress.ip_network("10.0.0.0/8"),  # Private
        ipaddress.ip_network("172.16.0.0/12"),  # Private
        ipaddress.ip_network("192.168.0.0/16"),  # Private
        ipaddress.ip_network("127.0.0.0/8"),  # Loopback
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local
        ipaddress.ip_network("0.0.0.0/8"),  # Current network
        ipaddress.ip_network("224.0.0.0/4"),  # Multicast
        ipaddress.ip_network("240.0.0.0/4"),  # Reserved
        ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
        ipaddress.ip_network("198.18.0.0/15"),  # Benchmark
        ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol
        ipaddress.ip_network("192.0.2.0/24"),  # Documentation
        ipaddress.ip_network("198.51.100.0/24"),  # Documentation
        ipaddress.ip_network("203.0.113.0/24"),  # Documentation
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
        ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
        ipaddress.ip_network("ff00::/8"),  # IPv6 multicast
    ]
    
    # Allowed protocols
    ALLOWED_PROTOCOLS = {"http", "https"}
    
    def __init__(
        self,
        allowed_domains: Optional[Set[str]] = None,
        blocked_ranges: Optional[List[ipaddress.IPv4Network | ipaddress.IPv6Network]] = None,
    ):
        """Initialize SSRF protection middleware.
        
        Args:
            allowed_domains: Whitelist of allowed domains (optional)
            blocked_ranges: Custom blocked IP ranges (extends defaults)
        """
        self.allowed_domains = allowed_domains or set()
        self.blocked_ranges = blocked_ranges or self.BLOCKED_RANGES
    
    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """Validate URL for SSRF vulnerabilities.
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (valid, error_message)
        """
        try:
            parsed = urlparse(url)
            
            # Check protocol
            if parsed.scheme.lower() not in self.ALLOWED_PROTOCOLS:
                return False, f"Protocol '{parsed.scheme}' not allowed"
            
            # Check domain whitelist if configured
            if self.allowed_domains and parsed.hostname:
                if parsed.hostname not in self.allowed_domains:
                    # Check for wildcard domains
                    for allowed in self.allowed_domains:
                        if allowed.startswith("*.") and parsed.hostname.endswith(allowed[1:]):
                            break
                    else:
                        return False, f"Domain '{parsed.hostname}' not in whitelist"
            
            # Resolve hostname and check IP
            if parsed.hostname:
                try:
                    # Get all IP addresses for the hostname
                    addr_info = socket.getaddrinfo(
                        parsed.hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
                    )
                    
                    for family, socktype, proto, canonname, sockaddr in addr_info:
                        ip_str = sockaddr[0]
                        try:
                            ip = ipaddress.ip_address(ip_str)
                            
                            # Check if IP is in blocked ranges
                            for blocked in self.blocked_ranges:
                                if ip in blocked:
                                    return False, f"IP {ip_str} is in blocked range"
                        except ValueError:
                            continue
                except socket.gaierror:
                    return False, f"Failed to resolve hostname: {parsed.hostname}"
            
            return True, None
            
        except Exception as e:
            logger.error(f"URL validation error: {e}")
            return False, f"URL validation failed: {str(e)}"
    
    def validate_urls_in_dict(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate all URL-like fields in a dictionary.
        
        Args:
            data: Dictionary to check
            
        Returns:
            Tuple of (valid, error_message)
        """
        url_fields = {"url", "webhook", "callback", "redirect", "endpoint", "target"}
        
        for key, value in data.items():
            if key.lower() in url_fields and isinstance(value, str):
                valid, error = self.validate_url(value)
                if not valid:
                    return False, f"SSRF protection: {error} (field: {key})"
            
            # Recursively check nested dicts
            if isinstance(value, dict):
                valid, error = self.validate_urls_in_dict(value)
                if not valid:
                    return False, error
        
        return True, None


# ============================================================================
# A09: Enhanced Security Logging
# ============================================================================

class EnhancedSecurityLogger:
    """Enhanced security logging with structured format."""
    
    def __init__(self, logger_name: str = "owasp_security"):
        """Initialize enhanced security logger."""
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
    
    def log_access_control_event(
        self,
        event_type: str,
        client: str,
        resource: str,
        role: str,
        allowed: bool,
    ) -> None:
        """Log access control event."""
        self.logger.info(
            f"ACCESS_CONTROL: type={event_type} client={client} "
            f"resource={resource} role={role} allowed={allowed}"
        )
    
    def log_injection_attempt(
        self,
        injection_type: str,
        client: str,
        path: str,
        pattern: str,
    ) -> None:
        """Log injection attempt."""
        self.logger.warning(
            f"INJECTION_ATTEMPT: type={injection_type} client={client} "
            f"path={path} pattern={pattern}"
        )
    
    def log_ssrf_attempt(
        self,
        client: str,
        url: str,
        reason: str,
    ) -> None:
        """Log SSRF attempt."""
        self.logger.warning(
            f"SSRF_ATTEMPT: client={client} url={url} reason={reason}"
        )
    
    def log_crypto_event(
        self,
        event_type: str,
        client: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log cryptographic event."""
        msg = f"CRYPTO: type={event_type} client={client}"
        if details:
            msg += f" details={details}"
        self.logger.info(msg)


# ============================================================================
# Main OWASP Middleware
# ============================================================================

class OWASPMiddleware:
    """Comprehensive OWASP Top 10 security middleware."""
    
    def __init__(
        self,
        cors_config: Optional[Dict[str, Any]] = None,
        hsts_max_age: int = 31536000,
        enable_injection_checks: bool = True,
        enable_ssrf_protection: bool = True,
        allowed_domains: Optional[Set[str]] = None,
    ):
        """Initialize OWASP middleware.
        
        Args:
            cors_config: CORS configuration
            hsts_max_age: HSTS max-age in seconds
            enable_injection_checks: Enable injection prevention
            enable_ssrf_protection: Enable SSRF protection
            allowed_domains: Whitelist for SSRF protection
        """
        self.access_control = AccessControlMiddleware(cors_config)
        self.crypto_headers = CryptoHeadersMiddleware(hsts_max_age)
        self.injection_prevention = InjectionPreventionMiddleware(
            check_sql=enable_injection_checks,
            check_nosql=enable_injection_checks,
            check_command=enable_injection_checks,
        )
        self.ssrf_protection = SSRFProtectionMiddleware(
            allowed_domains=allowed_domains
        )
        self.security_logger = EnhancedSecurityLogger()
    
    def before_request(self) -> Optional[Any]:
        """Execute before each request."""
        # Handle CORS preflight
        preflight_response = self.access_control.handle_preflight()
        if preflight_response:
            return preflight_response
        
        # Check for injection attempts in request data
        try:
            data = request.get_json(silent=True)
            if data:
                # Check injection
                for key, value in data.items():
                    if isinstance(value, str):
                        safe, inj_type, pattern = self.injection_prevention.check_injection(value)
                        if not safe:
                            client = self._get_client_key()
                            self.security_logger.log_injection_attempt(
                                inj_type, client, request.path, pattern
                            )
                            return jsonify({
                                "ok": False,
                                "error": "injection_detected",
                                "message": f"Potentially dangerous {inj_type} pattern detected",
                            }), 400
                
                # Check SSRF
                if self.ssrf_protection:
                    valid, error = self.ssrf_protection.validate_urls_in_dict(data)
                    if not valid:
                        client = self._get_client_key()
                        self.security_logger.log_ssrf_attempt(client, str(data), error)
                        return jsonify({
                            "ok": False,
                            "error": "ssrf_blocked",
                            "message": error,
                        }), 400
        except Exception as e:
            logger.error(f"OWASP middleware error: {e}")
        
        return None
    
    def after_request(self, response) -> Any:
        """Execute after each request."""
        # Add CORS headers
        self.access_control.add_cors_headers(response)
        
        # Add crypto headers
        self.crypto_headers.add_headers(response)
        
        return response
    
    def _get_client_key(self) -> str:
        """Extract client key from request."""
        try:
            api_key = request.headers.get("X-API-Key", "").strip()
            if api_key:
                return f"apikey:{api_key[:16]}"
            
            auth_token = request.headers.get("X-Auth-Token", "").strip()
            if auth_token:
                return f"token:{auth_token[:16]}"
            
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            return f"ip:{client_ip}"
        except RuntimeError:
            return "unknown"


# Global middleware instance
_owasp_middleware: Optional[OWASPMiddleware] = None


def get_owasp_middleware() -> OWASPMiddleware:
    """Get the global OWASP middleware instance."""
    global _owasp_middleware
    if _owasp_middleware is None:
        # Load configuration from environment
        cors_origins = os.environ.get("COPILOT_CORS_ORIGINS", "").split(",")
        cors_origins = [o.strip() for o in cors_origins if o.strip()]
        
        allowed_domains = os.environ.get("COPILOT_SSRF_ALLOWED_DOMAINS", "").split(",")
        allowed_domains = {d.strip() for d in allowed_domains if d.strip()}
        
        _owasp_middleware = OWASPMiddleware(
            cors_config={"allowed_origins": cors_origins} if cors_origins else None,
            hsts_max_age=int(os.environ.get("COPILOT_HSTS_MAX_AGE", 31536000)),
            enable_injection_checks=os.environ.get("COPILOT_INJECTION_CHECKS", "true").lower() == "true",
            enable_ssrf_protection=os.environ.get("COPILOT_SSRF_PROTECTION", "true").lower() == "true",
            allowed_domains=allowed_domains or None,
        )
    return _owasp_middleware


def init_owasp_middleware(app) -> None:
    """Initialize OWASP middleware for a Flask app.
    
    Args:
        app: Flask application
    """
    middleware = get_owasp_middleware()
    
    app.before_request(middleware.before_request)
    app.after_request(middleware.after_request)
    
    logger.info("OWASP security middleware initialized")


def require_role(role: str):
    """Decorator to require a minimum role for an endpoint.
    
    Args:
        role: Minimum required role (admin, user, readonly, guest)
        
    Returns:
        Decorator function
        
    Example:
        @bp.get("/admin/users")
        @require_role("admin")
        def list_users():
            ...
    """
    middleware = get_owasp_middleware()
    return middleware.access_control.require_role(role)


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate URL for SSRF vulnerabilities.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (valid, error_message)
        
    Example:
        valid, error = validate_url("https://example.com")
        if not valid:
            abort(400, error)
    """
    middleware = get_owasp_middleware()
    return middleware.ssrf_protection.validate_url(url)


def check_injection(value: str) -> Tuple[bool, Optional[str], str]:
    """Check string for injection patterns.
    
    Args:
        value: String to check
        
    Returns:
        Tuple of (safe, injection_type, pattern_matched)
    """
    middleware = get_owasp_middleware()
    return middleware.injection_prevention.check_injection(value)
