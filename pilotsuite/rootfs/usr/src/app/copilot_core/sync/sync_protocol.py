"""Sync Protocol — Secure communication layer for Multi-Home Sync.

Implements a request/response protocol over HTTPS for syncing configuration,
state, and events between home instances. Each message is signed with HMAC-SHA256.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class MessageType(str, Enum):
    """Sync protocol message types."""
    PING = "ping"
    PONG = "pong"
    PULL_CONFIG = "pull_config"
    PUSH_CONFIG = "push_config"
    PULL_STATE = "pull_state"
    PUSH_STATE = "push_state"
    HEARTBEAT = "heartbeat"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    ACK = "ack"
    ERROR = "error"


class SyncDirection(str, Enum):
    """Sync operation direction."""
    PULL = "pull"   # Fetch from remote
    PUSH = "push"   # Send to remote
    EXCHANGE = "exchange"  # Bidirectional


# -----------------------------------------------------------------------------


@dataclass
class SyncEnvelope:
    """Signed, versioned envelope wrapping all sync messages."""
    version: str = "1.0"
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    home_id: str = ""
    message_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)
    signature: str = ""

    def sign(self, secret: str) -> "SyncEnvelope":
        """Attach HMAC-SHA256 signature to this envelope."""
        sig_input = json.dumps(
            {
                "version": self.version,
                "message_id": self.message_id,
                "home_id": self.home_id,
                "message_type": self.message_type,
                "timestamp": self.timestamp,
                "payload": self.payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        self.signature = hmac.new(
            secret.encode("utf-8"),
            sig_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return self

    def verify(self, secret: str) -> bool:
        """Verify the envelope's HMAC signature."""
        if not self.signature:
            return False
        sig_input = json.dumps(
            {
                "version": self.version,
                "message_id": self.message_id,
                "home_id": self.home_id,
                "message_type": self.message_type,
                "timestamp": self.timestamp,
                "payload": self.payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        expected = hmac.new(
            secret.encode("utf-8"),
            sig_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "message_id": self.message_id,
            "home_id": self.home_id,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncEnvelope":
        return cls(
            version=data.get("version", "1.0"),
            message_id=data.get("message_id", ""),
            home_id=data.get("home_id", ""),
            message_type=data.get("message_type", ""),
            timestamp=data.get("timestamp", ""),
            payload=data.get("payload", {}),
            signature=data.get("signature", ""),
        )


@dataclass
class SyncResponse:
    """Standardized response from a sync operation."""
    ok: bool
    message_id: str
    message_type: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message_id": self.message_id,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_envelope(cls, env: SyncEnvelope, duration_ms: float = 0.0) -> "SyncResponse":
        return cls(
            ok=True,
            message_id=env.message_id,
            message_type=env.message_type,
            timestamp=env.timestamp,
            payload=env.payload,
            duration_ms=duration_ms,
        )

    @classmethod
    def error_response(
        cls,
        message_id: str,
        message_type: str,
        error: str,
    ) -> "SyncResponse":
        return cls(
            ok=False,
            message_id=message_id,
            message_type=message_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error=error,
        )


# -----------------------------------------------------------------------------


class SyncProtocol:
    """HTTP-based sync protocol client.

    Sends signed envelopes to remote home instances and processes responses.
    Timeout, retry, and backoff are handled internally.
    """

    DEFAULT_TIMEOUT = 15.0  # seconds
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 1.5

    def __init__(
        self,
        home_id: str,
        shared_secret: str,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.home_id = home_id
        self.shared_secret = shared_secret
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def send(
        self,
        remote_base_url: str,
        message_type: MessageType,
        payload: Optional[dict[str, Any]] = None,
    ) -> SyncResponse:
        """Send a signed envelope to a remote home and wait for a response."""
        envelope = SyncEnvelope(
            home_id=self.home_id,
            message_type=message_type.value,
            payload=payload or {},
        ).sign(self.shared_secret)

        url = f"{remote_base_url.rstrip('/')}/api/v1/multihome/rpc"
        last_error: Optional[str] = None
        wait_time = self.timeout

        for attempt in range(self.MAX_RETRIES):
            started = time.monotonic()
            try:
                resp = self._session.post(
                    url,
                    json=envelope.to_dict(),
                    timeout=wait_time,
                )
                duration_ms = (time.monotonic() - started) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        return SyncResponse(
                            ok=True,
                            message_id=envelope.message_id,
                            message_type=message_type.value,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            payload=data.get("payload", {}),
                            duration_ms=duration_ms,
                        )
                    else:
                        return SyncResponse.error_response(
                            envelope.message_id,
                            message_type.value,
                            data.get("error", "remote error"),
                        )
                elif resp.status_code >= 500:
                    last_error = f"server error {resp.status_code}"
                elif resp.status_code == 401:
                    return SyncResponse.error_response(
                        envelope.message_id,
                        message_type.value,
                        "unauthorized — check auth token",
                    )
                else:
                    return SyncResponse.error_response(
                        envelope.message_id,
                        message_type.value,
                        f"http {resp.status_code}",
                    )

            except requests.Timeout:
                last_error = f"timeout after {wait_time:.1f}s"
            except requests.ConnectionError:
                last_error = "connection refused"
            except Exception as e:
                last_error = str(e)

            if attempt < self.MAX_RETRIES - 1:
                wait_time = min(wait_time * self.BACKOFF_FACTOR, 60.0)
                logger.warning(
                    "SyncProtocol attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt + 1, self.MAX_RETRIES, last_error, wait_time,
                )
                time.sleep(wait_time)

        return SyncResponse.error_response(
            envelope.message_id,
            message_type.value,
            f"all {self.MAX_RETRIES} attempts failed: {last_error}",
        )

    def ping(self, remote_base_url: str) -> tuple[bool, Optional[float]]:
        """Lightweight reachability check. Returns (ok, latency_ms)."""
        started = time.monotonic()
        resp = self.send(remote_base_url, MessageType.PING, {})
        latency = (time.monotonic() - started) * 1000
        return resp.ok, latency

    def pull_config(
        self,
        remote_base_url: str,
        since: Optional[str] = None,
    ) -> SyncResponse:
        """Request full or incremental configuration snapshot from remote."""
        payload = {}
        if since:
            payload["since"] = since
        return self.send(remote_base_url, MessageType.PULL_CONFIG, payload)

    def push_config(
        self,
        remote_base_url: str,
        config_snapshot: dict[str, Any],
    ) -> SyncResponse:
        """Push a configuration snapshot to remote for merging."""
        return self.send(
            remote_base_url,
            MessageType.PUSH_CONFIG,
            {"config": config_snapshot},
        )

    def pull_state(
        self,
        remote_base_url: str,
        entity_ids: Optional[list[str]] = None,
    ) -> SyncResponse:
        """Request entity states from remote (optionally filtered)."""
        payload = {}
        if entity_ids:
            payload["entity_ids"] = entity_ids
        return self.send(remote_base_url, MessageType.PULL_STATE, payload)

    def push_state(
        self,
        remote_base_url: str,
        states: dict[str, Any],
    ) -> SyncResponse:
        """Push entity states to remote."""
        return self.send(
            remote_base_url,
            MessageType.PUSH_STATE,
            {"states": states},
        )

    def notify_conflict(
        self,
        remote_base_url: str,
        conflict_data: dict[str, Any],
    ) -> SyncResponse:
        """Notify remote of a detected conflict."""
        return self.send(
            remote_base_url,
            MessageType.CONFLICT_DETECTED,
            {"conflict": conflict_data},
        )

    # -------------------------------------------------------------------------
    # Server-side: handle incoming envelope (used by API endpoint)
    # -------------------------------------------------------------------------

    @staticmethod
    def verify_envelope(
        raw: dict[str, Any],
        secret: str,
    ) -> tuple[Optional[SyncEnvelope], Optional[str]]:
        """Verify and deserialize an incoming envelope.

        Returns (envelope, None) on success or (None, error_message) on failure.
        """
        try:
            env = SyncEnvelope.from_dict(raw)
        except Exception as e:
            return None, f"malformed envelope: {e}"

        if not env.verify(secret):
            return None, "signature mismatch"

        return env, None
