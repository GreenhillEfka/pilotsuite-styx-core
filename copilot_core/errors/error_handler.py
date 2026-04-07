"""P1-001: Error Handling Framework — Central Error Handler.

Features:
- Retry Logic mit Exponential Backoff
- Circuit Breaker Pattern
- Fallback Strategies
- Error Classification (Recoverable vs Fatal)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorSeverity(Enum):
    """Error classification for handling strategies."""
    RECOVERABLE = "recoverable"  # Retry possible
    DEGRADED = "degraded"  # Fallback available
    FATAL = "fatal"  # No recovery possible


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ErrorContext:
    """Context information for error handling."""
    operation: str
    error_type: str
    error_message: str
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE
    metadata: dict = field(default_factory=dict)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # seconds
    half_open_max_calls: int = 3


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_successes = 0

    def record_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.half_open_successes = 0
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker closed after successful test")
        self.state = CircuitState.CLOSED

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker opened after half-open failure")
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.config.failure_threshold:
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            self.state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if call can be executed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_failure_time is None:
                return True
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                logger.info("Circuit breaker entering half-open state")
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN state
        return self.half_open_successes < self.config.half_open_max_calls


class ErrorHandler:
    """Central error handler with retry, circuit breaker, and fallback."""

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = CircuitBreaker(
            circuit_breaker_config or CircuitBreakerConfig()
        )
        self._error_history: list[ErrorContext] = []
        self._fallbacks: dict[str, Callable] = {}

    def register_fallback(self, operation: str, fallback: Callable):
        """Register fallback handler for operation."""
        self._fallbacks[operation] = fallback
        logger.info(f"Registered fallback for operation: {operation}")

    async def execute_with_retry(
        self,
        operation: str,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """Execute function with retry logic."""
        if not self.circuit_breaker.can_execute():
            raise RuntimeError(f"Circuit breaker open for operation: {operation}")

        last_error: Optional[Exception] = None
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                last_error = e
                error_ctx = ErrorContext(
                    operation=operation,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    retry_count=attempt,
                    severity=ErrorSeverity.RECOVERABLE if attempt < self.retry_config.max_retries else ErrorSeverity.FATAL,
                )
                self._error_history.append(error_ctx)
                self.circuit_breaker.record_failure()

                if attempt >= self.retry_config.max_retries:
                    logger.error(f"Operation {operation} failed after {attempt + 1} attempts")
                    break

                # Calculate delay with exponential backoff
                delay = min(
                    self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
                    self.retry_config.max_delay
                )
                if self.retry_config.jitter:
                    import random
                    delay *= (0.5 + random.random())

                logger.warning(f"Retry {attempt + 1}/{self.retry_config.max_retries} for {operation} in {delay:.2f}s")
                await asyncio.sleep(delay)

        if last_error:
            # Try fallback if available
            if operation in self._fallbacks:
                logger.info(f"Using fallback for operation: {operation}")
                try:
                    return self._fallbacks[operation]()
                except Exception as fallback_error:
                    logger.error(f"Fallback failed for {operation}: {fallback_error}")
            raise last_error

        raise RuntimeError(f"Unexpected error in retry loop for {operation}")

    def get_error_history(self, limit: int = 100) -> list[ErrorContext]:
        """Get recent error history."""
        return self._error_history[-limit:]

    def clear_error_history(self):
        """Clear error history."""
        self._error_history.clear()


# Global default error handler
default_error_handler = ErrorHandler()


async def with_error_handling(
    operation: str,
    func: Callable[..., T],
    *args,
    **kwargs,
) -> T:
    """Convenience function for error-handled execution."""
    return await default_error_handler.execute_with_retry(operation, func, *args, **kwargs)
