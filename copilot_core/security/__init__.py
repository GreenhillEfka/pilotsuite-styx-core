"""Security module for PilotSuite Core.

Exposes pure-Core security helpers from the repo-root package while keeping
Flask-dependent add-on security surfaces optional.
"""
from __future__ import annotations

from pathlib import Path


_ADDON_SECURITY_PACKAGE = (
    Path(__file__).resolve().parents[2]
    / "addons"
    / "pilotsuite"
    / "app"
    / "copilot_core"
    / "security"
)
if _ADDON_SECURITY_PACKAGE.is_dir():
    addon_package_path = str(_ADDON_SECURITY_PACKAGE)
    if addon_package_path not in __path__:
        __path__.append(addon_package_path)

from .hardening import (
    APIKeyRecord,
    APIKeyStore,
    EncryptionAtRest,
    PasswordHasher,
    SecureTokenGenerator,
)
from .enhanced_security import (
    BehavioralBiometrics,
    HomomorphicEncryption,
    TokenVault,
    ZeroTrustPolicy,
    async_setup_enhanced_security,
)

__all__ = [
    "APIKeyRecord",
    "APIKeyStore",
    "EncryptionAtRest",
    "PasswordHasher",
    "SecureTokenGenerator",
    "BehavioralBiometrics",
    "HomomorphicEncryption",
    "TokenVault",
    "ZeroTrustPolicy",
    "async_setup_enhanced_security",
]

try:
    from .rate_limiter import RateLimiter, get_rate_limiter, rate_limit, get_rate_limit_status
    from .input_validator import InputValidator, validate_input, sanitize_input, get_validator
    from .security_logs import SecurityLogger, get_security_logger

    __all__.extend(
        [
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
            "WEB_SECURITY_AVAILABLE",
        ]
    )
    WEB_SECURITY_AVAILABLE = True
except ModuleNotFoundError:
    WEB_SECURITY_AVAILABLE = False

try:
    from .owasp_middleware import (
        AccessControlMiddleware,
        CryptoHeadersMiddleware,
        EnhancedSecurityLogger,
        InjectionPreventionMiddleware,
        OWASPMiddleware,
        SSRFProtectionMiddleware,
        check_injection,
        get_owasp_middleware,
        init_owasp_middleware,
        require_role,
        validate_url,
    )

    __all__.extend(
        [
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
    )
    OWASP_AVAILABLE = True
except ModuleNotFoundError:
    OWASP_AVAILABLE = False
