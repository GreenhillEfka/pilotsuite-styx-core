"""
Central Error Handling Framework for Copilot Core.

Provides:
- Centralized error handler with classification
- Retry logic with exponential backoff
- Circuit breaker pattern
- Fallback strategies
- Error classification (Recoverable vs Fatal)
"""

from .error_handler import (
    ErrorHandler,
    ErrorClassification,
    CircuitBreaker,
    RetryConfig,
    FallbackStrategy,
)

__all__ = [
    "ErrorHandler",
    "ErrorClassification",
    "CircuitBreaker",
    "RetryConfig",
    "FallbackStrategy",
]
