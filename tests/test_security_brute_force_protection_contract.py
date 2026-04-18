"""Contract test: brute-force protection for auth endpoints."""
from __future__ import annotations

import time
import pytest


class TestBruteForceIPProtection:
    """Per-IP brute-force locking."""

    def test_ip_lockout_after_max_failures(self):
        """IP gets locked after MAX_FAILED_PER_IP failures."""
        from copilot_core.security.brute_force_protection import (
            _bruteforce_store,
            _MAX_FAILED_PER_IP,
            _LOCK_DURATION_IP,
        )

        # Reset
        ip = "192.168.1.99"
        _bruteforce_store._ip_records.clear()

        # Fail MAX times
        for _ in range(_MAX_FAILED_PER_IP - 1):
            result = _bruteforce_store.record_ip_failure(ip)
            assert result is None  # not locked yet

        # MAXth failure triggers lock
        locked_until = _bruteforce_store.record_ip_failure(ip)
        assert locked_until is not None
        assert locked_until > time.time()

        # Check locked
        is_locked, _ = _bruteforce_store.check_ip(ip)
        assert is_locked is True

    def test_ip_success_resets_counter(self):
        """Successful auth resets the IP failure counter."""
        from copilot_core.security.brute_force_protection import _bruteforce_store

        ip = "192.168.1.100"
        _bruteforce_store._ip_records.clear()

        # Record some failures
        for _ in range(3):
            _bruteforce_store.record_ip_failure(ip)

        # Successful auth
        _bruteforce_store.record_success(ip)

        # Counter should be reset
        rec = _bruteforce_store._ip_records.get(ip)
        assert rec is None or rec.count == 0


class TestBruteForceTokenProtection:
    """Per-token-hint brute-force locking."""

    def test_token_lockout_after_max_failures(self):
        """Token hint gets locked after MAX_FAILED_PER_TOKEN failures."""
        from copilot_core.security.brute_force_protection import (
            _bruteforce_store,
            _MAX_FAILED_PER_TOKEN,
            _LOCK_DURATION_TOKEN,
        )

        # Reset
        hint = "deadbeefcafebabe"
        _bruteforce_store._token_records.clear()

        for _ in range(_MAX_FAILED_PER_TOKEN - 1):
            result = _bruteforce_store.record_token_failure(hint)
            assert result is None

        locked_until = _bruteforce_store.record_token_failure(hint)
        assert locked_until is not None
        assert locked_until > time.time()

        is_locked, _ = _bruteforce_store.check_token(hint)
        assert is_locked is True

    def test_token_success_resets_counter(self):
        """Successful auth resets the token failure counter."""
        from copilot_core.security.brute_force_protection import _bruteforce_store

        hint = "deadbeefcafebabe"
        _bruteforce_store._token_records.clear()

        for _ in range(3):
            _bruteforce_store.record_token_failure(hint)

        _bruteforce_store.record_success(hint, hint)

        rec = _bruteforce_store._token_records.get(hint)
        assert rec is None or rec.count == 0

