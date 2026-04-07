"""Security module for PilotSuite Styx Core.

Provides comprehensive security features:
- Input validation (SQL injection, XSS, path traversal)
- Rate limiting (token bucket algorithm)
- Security logging
- OWASP Top 10 2021 compliance middleware

Usage:
    from copilot_core.security import (
        get_validator,
        get_rate_limiter,
        get_security_logger,
        validate_input,
        rate_limit,
    )
    
    # Or use the OWASP middleware:
    from copilot_core.security.owasp_middleware import init_owasp_middleware
"""

# Try to import available security modules, skip if not available
InputValidator = None
get_validator = None
validate_input = None
sanitize_input = None

RateLimiter = None
TokenBucket = None
get_rate_limiter = None
rate_limit = None
get_rate_limit_status = None

SecurityLogger = None
get_security_logger = None

# Try importing input_validator
try:
    from .input_validator import (
        InputValidator,
        get_validator,
        validate_input,
        sanitize_input,
    )
except ImportError:
    pass

# Try importing rate_limiter
try:
    from .rate_limiter import (
        RateLimiter,
        TokenBucket,
        get_rate_limiter,
        rate_limit,
        get_rate_limit_status,
    )
except ImportError:
    pass

# Try importing security_logs
try:
    from .security_logs import (
        SecurityLogger,
        get_security_logger,
    )
except ImportError:
    pass

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
except ImportError as e:
    OWASP_AVAILABLE = False

__all__ = [
    # Input validation
    "InputValidator",
    "get_validator",
    "validate_input",
    "sanitize_input",
    
    # Rate limiting
    "RateLimiter",
    "TokenBucket",
    "get_rate_limiter",
    "rate_limit",
    "get_rate_limit_status",
    
    # Security logging
    "SecurityLogger",
    "get_security_logger",
    
    # OWASP middleware (if available)
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
