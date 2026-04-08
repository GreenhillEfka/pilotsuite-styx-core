"""Tests for Notification Engine (v5.8.0)."""

import pytest
import time
from copilot_core.notifications.engine import (
    NotificationEngine,
    Notification,
    NotificationDigest,
    Priority,
    DEFAULT_DEDUP_WINDOW_SECONDS,
)


@pytest.fixture
def engine():
    return NotificationEngine(
        dedup_window_seconds=2,
        rate_limit_per_hour=5,
        digest_interval_minutes=1,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Priority
# ═══════════════════════════════════════════════════════════════════════════


class TestPriority:
    def test_critical_is_1(self):
        assert Priority.CRITICAL == 1

    def test_ordering(self):
        assert Priority.CRITICAL < Priority.HIGH < Priority.NORMAL < Priority.LOW

    def test_names(self):
        assert Priority.CRITICAL.name == "CRITICAL"
        assert Priority.LOW.name == "LOW"


# ═══════════════════════════════════════════════════════════════════════════
# Basic Notify
# ═══════════════════════════════════════════════════════════════════════════


class TestBasicNotify:
    def test_notify_returns_notification(self, engine):
        n = engine.notify("energy", "Test", "Hello", Priority.NORMAL)
        assert isinstance(n, Notification)
        assert n.source == "energy"
        assert n.title == "Test"

    def test_notification_has_id(self, engine):
        n = engine.notify("energy", "Test", "Hello")
        assert n.id.startswith("n-")

    def test_notification_has_timestamp(self, engine):
        n = engine.notify("energy", "Test", "Hello")
        assert n.created_at is not None

    def test_default_priority_is_normal(self, engine):
        n = engine.notify("energy", "Test", "Hello")
        assert n.priority == Priority.NORMAL

    def test_custom_priority(self, engine):
        n = engine.notify("energy", "Alert", "Fire", Priority.CRITICAL)
        assert n.priority == Priority.CRITICAL

    def test_int_priority_converted(self, engine):
        n = engine.notify("energy", "Test", "Hello", priority=2)
        assert n.priority == Priority.HIGH

    def test_invalid_int_priority_defaults(self, engine):
        n = engine.notify("energy", "Test", "Hello", priority=99)
        assert n.priority == Priority.NORMAL

    def test_data_attached(self, engine):
        n = engine.notify("energy", "Test", "Hello", data={"device": "washer"})
        assert n.data["device"] == "washer"

    def test_channel_default(self, engine):
        n = engine.notify("energy", "Test", "Hello")
        assert n.channel == "default"

    def test_custom_channel(self, engine):
        n = engine.notify("energy", "Test", "Hello", channel="telegram")
        assert n.channel == "telegram"


# ═══════════════════════════════════════════════════════════════════════════
# Deduplication
# ═══════════════════════════════════════════════════════════════════════════


class TestDeduplication:
    def test_duplicate_rejected(self, engine):
        n1 = engine.notify("energy", "Same", "Message")
        n2 = engine.notify("energy", "Same", "Message")
        assert n1 is not None
        assert n2 is None

    def test_different_messages_not_deduped(self, engine):
        n1 = engine.notify("energy", "Title", "Message A")
        n2 = engine.notify("energy", "Title", "Message B")
        assert n1 is not None
        assert n2 is not None

    def test_custom_dedup_key(self, engine):
        n1 = engine.notify("energy", "A", "B", dedup_key="same")
        n2 = engine.notify("comfort", "C", "D", dedup_key="same")
        assert n1 is not None
        assert n2 is None

    def test_critical_bypasses_dedup(self, engine):
        n1 = engine.notify("energy", "Fire", "Now", Priority.CRITICAL)
        n2 = engine.notify("energy", "Fire", "Now", Priority.CRITICAL)
        assert n1 is not None
        assert n2 is not None

    def test_dedup_expires(self, engine):
        # Engine has 2-second dedup window
        n1 = engine.notify("energy", "Temp", "Alert")
        assert n1 is not None
        time.sleep(2.1)
        n2 = engine.notify("energy", "Temp", "Alert")
        assert n2 is not None


# ═══════════════════════════════════════════════════════════════════════════
# Rate Limiting
# ═══════════════════════════════════════════════════════════════════════════


class TestRateLimiting:
    def test_within_limit_accepted(self, engine):
        results = []
        for i in range(5):
            results.append(engine.notify("energy", f"Title {i}", f"Msg {i}"))
        assert all(r is not None for r in results)

    def test_exceeds_limit_rejected(self, engine):
        # Rate limit is 5/hour
        for i in range(5):
            engine.notify("energy", f"Title {i}", f"Msg {i}")
        n6 = engine.notify("energy", "Title 6", "Msg 6")
        assert n6 is None

    def test_critical_bypasses_rate_limit(self, engine):
        for i in range(5):
            engine.notify("energy", f"Title {i}", f"Msg {i}")
        n6 = engine.notify("energy", "FIRE", "HELP", Priority.CRITICAL)
        assert n6 is not None

    def test_different_channels_independent(self, engine):
        for i in range(5):
            engine.notify("energy", f"T {i}", f"M {i}", channel="ch1")
        # ch2 has its own limit
        n = engine.notify("energy", "New", "Alert", channel="ch2")
        assert n is not None


# ═══════════════════════════════════════════════════════════════════════════
# History
# ═══════════════════════════════════════════════════════════════════════════


class TestHistory:
    def test_history_tracks_notifications(self, engine):
        engine.notify("energy", "A", "1")
        engine.notify("comfort", "B", "2")
        history = engine.get_history()
        assert len(history) == 2

    def test_history_limit(self, engine):
        for i in range(10):
            engine.notify("energy", f"T{i}", f"M{i}")
        history = engine.get_history(limit=3)
        assert len(history) <= 3

    def test_history_filter_by_source(self, engine):
        engine.notify("energy", "A", "1")
        engine.notify("comfort", "B", "2")
        engine.notify("energy", "C", "3")
        history = engine.get_history(source="energy")
        assert len(history) == 2
        assert all(h["source"] == "energy" for h in history)

    def test_history_most_recent_first(self, engine):
        engine.notify("energy", "First", "1")
        engine.notify("energy", "Second", "2")
        history = engine.get_history()
        assert history[0]["title"] == "Second"

    def test_history_has_required_fields(self, engine):
        engine.notify("energy", "Test", "Message")
        h = engine.get_history()[0]
        assert "id" in h
        assert "source" in h
        assert "title" in h
        assert "message" in h
        assert "priority" in h
        assert "created_at" in h


# ═══════════════════════════════════════════════════════════════════════════
# Digest
# ═══════════════════════════════════════════════════════════════════════════


class TestDigest:
    def test_digest_empty(self, engine):
        digest = engine.get_digest()
        assert digest.count == 0

    def test_digest_counts_by_source(self, engine):
        engine.notify("energy", "A", "1")
        engine.notify("comfort", "B", "2")
        engine.notify("energy", "C", "3")
        digest = engine.get_digest()
        assert digest.by_source["energy"] == 2
        assert digest.by_source["comfort"] == 1

    def test_digest_counts_by_priority(self, engine):
        engine.notify("energy", "A", "1", Priority.CRITICAL)
        engine.notify("energy", "B", "2", Priority.NORMAL)
        digest = engine.get_digest()
        assert "CRITICAL" in digest.by_priority
        assert "NORMAL" in digest.by_priority

    def test_digest_has_items(self, engine):
        engine.notify("energy", "Test", "Hello")
        digest = engine.get_digest()
        assert len(digest.items) == 1
        assert digest.items[0]["title"] == "Test"


# ═══════════════════════════════════════════════════════════════════════════
# Pending / Flush
# ═══════════════════════════════════════════════════════════════════════════


class TestPending:
    def test_flush_returns_normal_priority(self, engine):
        engine.notify("energy", "Alert", "Check now", Priority.NORMAL)
        pending = engine.flush_pending()
        assert len(pending) == 1
        assert pending[0].title == "Alert"

    def test_flush_clears_pending(self, engine):
        engine.notify("energy", "Alert", "Check now")
        engine.flush_pending()
        pending = engine.flush_pending()
        assert len(pending) == 0

    def test_low_priority_goes_to_digest(self, engine):
        engine.notify("energy", "Tip", "Save energy", Priority.LOW)
        pending = engine.flush_pending()
        # LOW goes to digest buffer, not pending
        assert all(p.priority != Priority.LOW or "digest" in p.id for p in pending)

    def test_critical_in_pending(self, engine):
        engine.notify("energy", "FIRE", "HELP", Priority.CRITICAL)
        pending = engine.flush_pending()
        assert len(pending) == 1
        assert pending[0].priority == Priority.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════════════


class TestStats:
    def test_stats_structure(self, engine):
        stats = engine.get_stats()
        assert "total_notifications" in stats
        assert "pending_count" in stats
        assert "rate_limit_per_hour" in stats
        assert "dedup_window_seconds" in stats

    def test_stats_update_after_notify(self, engine):
        engine.notify("energy", "Test", "Hello")
        stats = engine.get_stats()
        assert stats["total_notifications"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Clear
# ═══════════════════════════════════════════════════════════════════════════


class TestClear:
    def test_clear_resets_all(self, engine):
        engine.notify("energy", "Test", "Hello")
        engine.clear_history()
        assert engine.get_history() == []
        assert engine.get_stats()["total_notifications"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Handler Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestHandlers:
    def test_register_handler(self, engine):
        engine.register_handler("telegram", lambda n: None)
        stats = engine.get_stats()
        assert "telegram" in stats["channels"]
