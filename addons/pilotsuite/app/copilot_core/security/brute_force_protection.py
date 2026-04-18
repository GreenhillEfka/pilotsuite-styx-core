"""Brute-Force Protection for API Authentication.

Implements per-IP and per-token failed-attempt rate limiting to prevent
credential stuffing and brute-force attacks on the auth endpoint.

Based on OWASP Cheat Sheet: Authentication.
"""

from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from flask import jsonify, request, g

_LOGGER = logging.getLogger(__name__)

# --- Config ---------------------------------------------------------------

_MAX_FAILED_PER_IP = 10          # lock IP after this many failures
_WINDOW_SECONDS_IP = 600        # 10-minute sliding window per IP
_LOCK_DURATION_IP = 300         # 5-minute lockout per IP

_MAX_FAILED_PER_TOKEN = 5        # lock token after this many failures
_WINDOW_SECONDS_TOKEN = 300     # 5-minute sliding window per token
_LOCK_DURATION_TOKEN = 600      # 10-minute lockout per token

# --- Data structures ------------------------------------------------------

@dataclass
class FailureRecord:
    """Tracks failed auth attempts for one subject (IP or token)."""
    count: int = 0
    first_failure_at: float = 0.0
    locked_until: float = 0.0

    def is_locked(self, now: float) -> bool:
        return now < self.locked_until

    def lock(self, duration: float, now: float) -> None:
        self.locked_until = now + duration
        self.count = 0
        self.first_failure_at = 0.0

    def record_failure(self, window: float, now: float) -> None:
        if self.first_failure_at == 0.0:
            self.first_failure_at = now
        self.count += 1
        # Reset if window expired
        if now - self.first_failure_at > window:
            self.count = 1
            self.first_failure_at = now

    def reset(self) -> None:
        self.count = 0
        self.first_failure_at = 0.0
        self.locked_until = 0.0


# --- Store ---------------------------------------------------------------

class _BruteForceStore:
    """Thread-safe store for failure records."""

    def __init__(self) -> None:
        self._ip_records: dict[str, FailureRecord] = {}
        self._token_records: dict[str, FailureRecord] = {}
        self._lock = threading.Lock()
        self._last_cleanup = 0.0
        self._cleanup_interval = 300.0  # clean up every 5 min

    def _cleanup(self, now: float) -> None:
        """Remove expired records to prevent memory growth."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        expired_ips = [
            k for k, v in self._ip_records.items()
            if now > v.locked_until and now - v.first_failure_at > _WINDOW_SECONDS_IP
        ]
        expired_tokens = [
            k for k, v in self._token_records.items()
            if now > v.locked_until and now - v.first_failure_at > _WINDOW_SECONDS_TOKEN
        ]
        for k in expired_ips:
            del self._ip_records[k]
        for k in expired_tokens:
            del self._token_records[k]

    def _get_ip_record(self, ip: str, now: float) -> FailureRecord:
        self._cleanup(now)
        with self._lock:
            if ip not in self._ip_records:
                self._ip_records[ip] = FailureRecord()
            return self._ip_records[ip]

    def _get_token_record(self, token_hint: str, now: float) -> FailureRecord:
        self._cleanup(now)
        with self._lock:
            if token_hint not in self._token_records:
                self._token_records[token_hint] = FailureRecord()
            return self._token_records[token_hint]

    def record_ip_failure(self, ip: str) -> Optional[float]:
        """Record one failed auth attempt from *ip*.

        Returns lockout-until timestamp if IP was just locked, else None.
        """
        now = time.time()
        rec = self._get_ip_record(ip, now)
        with self._lock:
            rec.record_failure(_WINDOW_SECONDS_IP, now)
            if rec.count >= _MAX_FAILED_PER_IP and not rec.is_locked(now):
                rec.lock(_LOCK_DURATION_IP, now)
                _LOGGER.warning("IP %s locked out for %ds (%d failures in %ds)",
                               ip, _LOCK_DURATION_IP, _MAX_FAILED_PER_IP, _WINDOW_SECONDS_IP)
                return rec.locked_until
        return None

    def check_ip(self, ip: str) -> tuple[bool, Optional[float]]:
        """Check if *ip* is currently locked.

        Returns (is_locked, locked_until).
        """
        now = time.time()
        rec = self._get_ip_record(ip, now)
        if rec.is_locked(now):
            return True, rec.locked_until
        return False, None

    def record_token_failure(self, token_hint: str) -> Optional[float]:
        """Record one failed auth attempt for *token_hint*.

        Returns lockout-until timestamp if token was just locked, else None.
        """
        now = time.time()
        rec = self._get_token_record(token_hint, now)
        with self._lock:
            rec.record_failure(_WINDOW_SECONDS_TOKEN, now)
            if rec.count >= _MAX_FAILED_PER_TOKEN and not rec.is_locked(now):
                rec.lock(_LOCK_DURATION_TOKEN, now)
                _LOGGER.warning("Token hint %s locked out for %ds (%d failures in %ds)",
                               token_hint[:8] + "...", _LOCK_DURATION_TOKEN,
                               _MAX_FAILED_PER_TOKEN, _WINDOW_SECONDS_TOKEN)
                return rec.locked_until
        return None

    def check_token(self, token_hint: str) -> tuple[bool, Optional[float]]:
        """Check if *token_hint* is currently locked."""
        now = time.time()
        rec = self._get_token_record(token_hint, now)
        if rec.is_locked(now):
            return True, rec.locked_until
        return False, None

    def record_success(self, ip: str, token_hint: Optional[str] = None) -> None:
        """Reset failure counters on successful auth."""
        now = time.time()
        with self._lock:
            if ip in self._ip_records:
                self._ip_records[ip].reset()
            if token_hint and token_hint in self._token_records:
                self._token_records[token_hint].reset()


_bruteforce_store = _BruteForceStore()


# --- Flask integration ---------------------------------------------------

def check_auth_lockout() -> tuple[bool, Optional[dict]]:
    """Call at the start of any auth-check view.

    Returns (blocked, response_dict).  If blocked is True the caller
    should return the dict as a 429/403 response immediately.
    """
    ip = (request.headers.get("X-Forwarded-For", "") or request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()

    is_locked, locked_until = _bruteforce_store.check_ip(ip)
    if is_locked:
        import math
        retry_after = max(1, int(math.ceil(locked_until - time.time())))
        return True, jsonify({
            "ok": False,
            "error": "Too many failed attempts",
            "message": f"IP temporarily locked. Retry after {retry_after}s.",
            "retry_after": retry_after,
        }), 429

    # Check token-level lockout (using a hash hint so we never store real tokens)
    import hashlib
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        token_hint = hashlib.sha256(auth_header[7:].encode()).hexdigest()[:16]
    else:
        token_hint = None

    if token_hint:
        is_tlocked, tlocked_until = _bruteforce_store.check_token(token_hint)
        if is_tlocked:
            import math
            retry_after = max(1, int(math.ceil(tlocked_until - time.time())))
            return True, jsonify({
                "ok": False,
                "error": "Token locked",
                "message": f"Token locked due to failed attempts. Retry after {retry_after}s.",
                "retry_after": retry_after,
            }), 429

    return False, None


def record_auth_failure() -> None:
    """Call when an auth attempt has failed (invalid token)."""
    ip = (request.headers.get("X-Forwarded-For", "") or request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()
    _bruteforce_store.record_ip_failure(ip)

    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        import hashlib
        token_hint = hashlib.sha256(auth_header[7:].encode()).hexdigest()[:16]
        _bruteforce_store.record_token_failure(token_hint)


def record_auth_success() -> None:
    """Call when an auth attempt succeeded."""
    ip = (request.headers.get("X-Forwarded-For", "") or request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()
    auth_header = (request.headers.get("Authorization") or "").strip()
    token_hint = None
    if auth_header.startswith("Bearer "):
        import hashlib
        token_hint = hashlib.sha256(auth_header[7:].encode()).hexdigest()[:16]
    _bruteforce_store.record_success(ip, token_hint)