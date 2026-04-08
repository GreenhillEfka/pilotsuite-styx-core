"""Security module for PilotSuite Styx Core.

Provides rate limiting, input validation, security middleware,
and OWASP Top 10 2021 compliance tools.
"""

from .rate_limiter import RateLimiter, get_rate_limiter, rate_limit, get_rate_limit_status
from .input_validator import InputValidator, validate_input, sanitize_input, get_validator
from .security_logs import SecurityLogger, get_security_logger

# OWASP middleware (optional import)
try:
    from .owasp_middleware import (
        OWASPMiddleware,
        AccessControlMiddleware,
        InjectionPreventionMiddleware,
        SSRFProtectionMiddleware,
        CryptoHeadersMiddleware,
        EnhancedSecurityLogger,
        init_owasp_middleware,
        require_role,
        validate_url,
        check_injection,
        get_owasp_middleware,
    )
    OWASP_AVAILABLE = True
except ImportError:
    OWASP_AVAILABLE = False

__all__ = [
    "RateLimiter",
    "get_rate_limiter",
    "rate_limit",
    "get_rate_limit_status",
    "InputValidator",
    "validate_input",
    "sanitize_input",
    "get_validator",
    "SecurityLogger",
    "get_security_logger",
    # OWASP middleware
    "OWASPMiddleware",
    "AccessControlMiddleware",
    "InjectionPreventionMiddleware",
    "SSRFProtectionMiddleware",
    "CryptoHeadersMiddleware",
    "EnhancedSecurityLogger",
    "init_owasp_middleware",
    "require_role",
    "validate_url",
    "check_injection",
    "get_owasp_middleware",
    "OWASP_AVAILABLE",
]
