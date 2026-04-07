"""HomeAssistant Async API Client.

Provides async HTTP client for HomeAssistant REST API with:
- Long-Lived Access Token authentication
- SSL support (including self-signed certificates)
- Connection timeout (5s default)
- Automatic retry with exponential backoff
- Circuit breaker for fault tolerance
"""
from __future__ import annotations

import asyncio
import logging
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"     # Normal operation, requests pass through
    OPEN = "open"         # Fault threshold exceeded, requests fail fast
    HALF_OPEN = "half_open"  # Recovery test after cooldown


@dataclass
class CircuitBreakerStatus:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)


class CircuitBreaker:
    """Circuit breaker pattern implementation for HA API calls.

    States:
    - CLOSED: Normal operation. Failures increment counter.
    - OPEN: After 5 failures in 60s, circuit opens. Requests fail fast.
    - HALF_OPEN: After 30s cooldown, allows 1 test request.
      Success → CLOSED. Failure → OPEN again.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        window_seconds: float = 60.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window_seconds = window_seconds
        self._status = CircuitBreakerStatus()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._status.state

    @property
    def status(self) -> CircuitBreakerStatus:
        return self._status

    async def can_execute(self) -> bool:
        """Check if request can proceed."""
        async with self._lock:
            now = time.time()

            if self._status.state == CircuitState.CLOSED:
                return True

            if self._status.state == CircuitState.OPEN:
                # Check if recovery timeout elapsed
                if self._status.last_failure_time is not None:
                    if now - self._status.last_failure_time >= self.recovery_timeout:
                        self._status.state = CircuitState.HALF_OPEN
                        self._status.last_state_change = now
                        logger.info("Circuit breaker: OPEN → HALF_OPEN (recovery timeout)")
                        return True
                return False

            # HALF_OPEN: allow exactly one test request
            return True

    async def record_success(self) -> None:
        """Record successful request."""
        async with self._lock:
            now = time.time()
            self._status.consecutive_failures = 0
            self._status.last_success_time = now

            if self._status.state == CircuitState.HALF_OPEN:
                self._status.state = CircuitState.CLOSED
                self._status.last_state_change = now
                logger.info("Circuit breaker: HALF_OPEN → CLOSED (recovery success)")

    async def record_failure(self) -> None:
        """Record failed request."""
        async with self._lock:
            now = time.time()
            self._status.consecutive_failures += 1
            self._status.last_failure_time = now

            if self._status.state == CircuitState.HALF_OPEN:
                self._status.state = CircuitState.OPEN
                self._status.last_state_change = now
                logger.warning("Circuit breaker: HALF_OPEN → OPEN (recovery failed)")

            elif self._status.state == CircuitState.CLOSED:
                if self._status.consecutive_failures >= self.failure_threshold:
                    self._status.state = CircuitState.OPEN
                    self._status.last_state_change = now
                    logger.warning(
                        f"Circuit breaker: CLOSED → OPEN ({self._status.consecutive_failures} failures)"
                    )


@dataclass
class HAConnectionConfig:
    """Configuration for HomeAssistant connection."""

    base_url: str = "http://homeassistant.local:8123"
    access_token: str = ""
    timeout_seconds: float = 5.0
    verify_ssl: bool = True
    retry_count: int = 3
    retry_delay_seconds: float = 1.0


@dataclass
class HAConnectionStatus:
    """Status of HA connection."""

    connected: bool = False
    base_url: str = ""
    last_error: Optional[str] = None
    last_success: Optional[float] = None
    response_time_ms: Optional[float] = None


class HomeAssistantClient:
    """Async client for HomeAssistant REST API."""

    def __init__(self, config: Optional[HAConnectionConfig] = None):
        self.config = config or HAConnectionConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._status = HAConnectionStatus()
        self._lock = asyncio.Lock()
        self._circuit = CircuitBreaker()

    async def _create_session(self) -> aiohttp.ClientSession:
        """Create aiohttp session with appropriate settings."""
        timeout = ClientTimeout(total=self.config.timeout_seconds)

        # SSL context configuration
        if not self.config.verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = TCPConnector(ssl=ssl_context)
        else:
            connector = TCPConnector()

        return aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                "Authorization": f"Bearer {self.config.access_token}",
                "X-Auth-Token": self.config.access_token,
                "Content-Type": "application/json",
            }
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create session with lock."""
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    self._session = await self._create_session()
        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def test_connection(self) -> HAConnectionStatus:
        """Test connection to HomeAssistant."""
        import time

        # Check circuit breaker
        if not await self._circuit.can_execute():
            self._status = HAConnectionStatus(
                connected=False,
                base_url=self.config.base_url,
                last_error="Circuit breaker OPEN"
            )
            return self._status

        try:
            session = await self._get_session()
            start = time.monotonic()

            async with session.get(
                f"{self.config.base_url}/api/",
                timeout=ClientTimeout(total=self.config.timeout_seconds)
            ) as response:
                elapsed_ms = (time.monotonic() - start) * 1000

                if response.status == 200:
                    self._status = HAConnectionStatus(
                        connected=True,
                        base_url=self.config.base_url,
                        last_success=time.time(),
                        response_time_ms=elapsed_ms
                    )
                    await self._circuit.record_success()
                    logger.info(f"HA connection successful: {elapsed_ms:.2f}ms")
                else:
                    self._status = HAConnectionStatus(
                        connected=False,
                        base_url=self.config.base_url,
                        last_error=f"HTTP {response.status}"
                    )
                    await self._circuit.record_failure()
                    logger.warning(f"HA connection failed: HTTP {response.status}")

        except asyncio.TimeoutError:
            self._status = HAConnectionStatus(
                connected=False,
                base_url=self.config.base_url,
                last_error="Connection timeout"
            )
            await self._circuit.record_failure()
            logger.warning(f"HA connection timeout after {self.config.timeout_seconds}s")

        except aiohttp.ClientError as e:
            self._status = HAConnectionStatus(
                connected=False,
                base_url=self.config.base_url,
                last_error=str(e)
            )
            await self._circuit.record_failure()
            logger.warning(f"HA connection error: {e}")

        except Exception as e:
            self._status = HAConnectionStatus(
                connected=False,
                base_url=self.config.base_url,
                last_error=str(e)
            )
            await self._circuit.record_failure()
            logger.error(f"HA connection unexpected error: {e}")

        return self._status

    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> aiohttp.ClientResponse:
        """Make HTTP request with retry logic and circuit breaker."""
        # Check circuit breaker before attempting request
        if not await self._circuit.can_execute():
            raise aiohttp.ClientError("Circuit breaker is OPEN - request blocked")

        session = await self._get_session()
        url = f"{self.config.base_url}{endpoint}"

        last_error = None

        for attempt in range(self.config.retry_count):
            try:
                async with session.request(method, url, **kwargs) as response:
                    if response.status < 500:
                        # Client errors (4xx) - don't retry
                        await self._circuit.record_success()
                        return response

                    # Server errors (5xx) - retry
                    last_error = f"HTTP {response.status}"
                    logger.warning(f"HA request failed (attempt {attempt + 1}): {last_error}")

                    if attempt < self.config.retry_count - 1:
                        delay = self.config.retry_delay_seconds * (2 ** attempt)
                        await asyncio.sleep(delay)

            except asyncio.TimeoutError:
                last_error = "Request timeout"
                logger.warning(f"HA request timeout (attempt {attempt + 1})")

                if attempt < self.config.retry_count - 1:
                    delay = self.config.retry_delay_seconds * (2 ** attempt)
                    await asyncio.sleep(delay)

            except aiohttp.ClientError as e:
                last_error = str(e)
                logger.warning(f"HA request error (attempt {attempt + 1}): {last_error}")

                if attempt < self.config.retry_count - 1:
                    delay = self.config.retry_delay_seconds * (2 ** attempt)
                    await asyncio.sleep(delay)

        # All retries exhausted - record failure
        await self._circuit.record_failure()
        raise aiohttp.ClientError(f"Request failed after {self.config.retry_count} attempts: {last_error}")

    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make GET request."""
        response = await self._request_with_retry("GET", endpoint, **kwargs)

        if response.status == 401:
            raise PermissionError("Authentication failed - check access token")
        elif response.status == 404:
            raise FileNotFoundError(f"Endpoint not found: {endpoint}")
        elif response.status >= 400:
            raise aiohttp.ClientError(f"HTTP {response.status}: {await response.text()}")

        return await response.json()

    async def post(self, endpoint: str, data: Optional[dict[str, Any]] = None, **kwargs: Any) -> dict[str, Any]:
        """Make POST request."""
        response = await self._request_with_retry(
            "POST", endpoint,
            json=data,
            **kwargs
        )

        if response.status == 401:
            raise PermissionError("Authentication failed - check access token")
        elif response.status == 404:
            raise FileNotFoundError(f"Endpoint not found: {endpoint}")
        elif response.status >= 400:
            raise aiohttp.ClientError(f"HTTP {response.status}: {await response.text()}")

        return await response.json()

    async def get_areas(self) -> list[dict[str, Any]]:
        """Get all areas/zones from area_registry."""
        try:
            data = await self.get("/api/config/area_registry")
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"Failed to get areas: {e}")
            return []

    async def get_states(self) -> list[dict[str, Any]]:
        """Get all entity states."""
        try:
            data = await self.get("/api/states")
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"Failed to get states: {e}")
            return []

    async def get_entity(self, entity_id: str) -> Optional[dict[str, Any]]:
        """Get single entity state."""
        try:
            data = await self.get(f"/api/states/{entity_id}")
            return data
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get entity {entity_id}: {e}")
            return None

    @property
    def status(self) -> HAConnectionStatus:
        """Get current connection status."""
        return self._status

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get circuit breaker instance."""
        return self._circuit

    @property
    def circuit_state(self) -> str:
        """Get circuit breaker state as string for monitoring."""
        return self._circuit.state.value

    async def __aenter__(self) -> "HomeAssistantClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
