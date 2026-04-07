"""Tests for Notification Intelligence (v7.2.0)."""

import pytest
from datetime import datetime, timedelta, timezone
from copilot_core.hub.notification_intelligence import (
    NotificationIntelligenceEngine,
    Notification,
    Priority,
    Channel,
    NotificationStats,
    NotificationIntelligenceDashboard,
)


@pytest.fixture
def engine():
    return NotificationIntelligenceEngine()


# ── Basic send ──────────────────────────────────────────────────────────────


class TestSend:
    def test_send_basic(self, engine):
        n = engine.send("Test", "Hello World")
        assert n.notification_id == "notif_1"
        assert n.delivered is True
        assert n.priority == Priority.NORMAL

    def test_send_with_priority(self, engine):
        n = engine.send("Alert", "Fire!", priority="critical")
        assert n.priority == Priority.CRITICAL

    def test_send_with_channel(self, engine):
        n = engine.send("TTS", "Guten Morgen", channel="tts")
        assert n.channel == Channel.TTS

    def test_send_increments_id(self, engine):
        n1 = engine.send("A", "a")
        n2 = engine.send("B", "b")
        assert n1.notification_id != n2.notification_id

    def test_notifications_capped(self, engine):
        for i in range(600):
            engine.send(f"N{i}", f"msg{i}")
        assert len(engine._notifications) == 500


# ── DND ─────────────────────────────────────────────────────────────────────


class TestDnd:
    def test_dnd_suppresses(self, engine):
        engine.set_dnd(enabled=True)
        n = engine.send("Test", "Suppressed")
        assert n.suppressed is True
        assert n.suppression_reason == "DND aktiv"

    def test_dnd_allows_critical(self, engine):
        engine.set_dnd(enabled=True, allow_critical=True)
        n = engine.send("Emergency", "Critical!", priority="critical")
        assert n.suppressed is False
        assert n.delivered is True

    def test_dnd_blocks_critical_when_disabled(self, engine):
        engine.set_dnd(enabled=True, allow_critical=False)
        n = engine.send("Emergency", "Critical!", priority="critical")
        assert n.suppressed is True

    def test_dnd_per_person(self, engine):
        engine.set_dnd(enabled=True, person_id="alice")
        n1 = engine.send("Test", "For alice", person_id="alice")
        n2 = engine.send("Test", "For bob", person_id="bob")
        assert n1.suppressed is True
        assert n2.suppressed is False

    def test_dnd_with_duration(self, engine):
        engine.set_dnd(enabled=True, duration_min=60)
        dnd_list = engine.get_dnd_status()
        assert len(dnd_list) == 1
        assert dnd_list[0]["until"] is not None

    def test_dnd_disable(self, engine):
        engine.set_dnd(enabled=True)
        engine.set_dnd(enabled=False)
        n = engine.send("Test", "Should deliver")
        assert n.delivered is True

    def test_dnd_expired(self, engine):
        engine.set_dnd(enabled=True, duration_min=1)
        # Simulate expiration
        engine._dnd_configs[0].until = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
        n = engine.send("Test", "DND expired")
        assert n.suppressed is False


# ── Batching ────────────────────────────────────────────────────────────────


class TestBatching:
    def test_batch_config(self, engine):
        cfg = engine.configure_batching(enabled=True, interval_min=30)
        assert cfg.enabled is True
        assert cfg.interval_min == 30

    def test_batch_queues_normal(self, engine):
        engine.configure_batching(enabled=True)
        n = engine.send("Low", "Batch this", priority="normal")
        assert n.batched is True
        assert len(engine._batch_queue) == 1

    def test_batch_skips_critical(self, engine):
        engine.configure_batching(enabled=True)
        n = engine.send("Urgent", "Don't batch", priority="critical")
        assert n.batched is False
        assert n.delivered is True

    def test_batch_skips_high(self, engine):
        engine.configure_batching(enabled=True)
        n = engine.send("High", "Don't batch", priority="high")
        assert n.batched is False

    def test_flush_batch(self, engine):
        engine.configure_batching(enabled=True)
        engine.send("A", "a")
        engine.send("B", "b")
        delivered = engine.flush_batch()
        assert len(delivered) == 2
        assert all(n.delivered for n in delivered)
        assert len(engine._batch_queue) == 0

    def test_batch_category_filter(self, engine):
        engine.configure_batching(enabled=True, categories=["info"])
        n1 = engine.send("Info", "batch", category="info", priority="normal")
        n2 = engine.send("Alert", "no batch", category="alert", priority="normal")
        assert n1.batched is True
        assert n2.batched is False


# ── Rules ───────────────────────────────────────────────────────────────────


class TestRules:
    def test_add_rule(self, engine):
        assert engine.add_rule("r1", "TTS Rule", channel="tts") is True
        assert len(engine.get_rules()) == 1

    def test_add_duplicate_rule(self, engine):
        engine.add_rule("r1", "Rule 1")
        assert engine.add_rule("r1", "Rule 2") is False

    def test_remove_rule(self, engine):
        engine.add_rule("r1", "Rule")
        assert engine.remove_rule("r1") is True
        assert len(engine.get_rules()) == 0

    def test_remove_unknown_rule(self, engine):
        assert engine.remove_rule("unknown") is False

    def test_rule_routes_channel(self, engine):
        engine.add_rule("r1", "TTS for security", category="security", channel="tts")
        n = engine.send("Alert", "Door open", category="security")
        assert n.channel == Channel.TTS

    def test_rule_priority_filter(self, engine):
        engine.add_rule("r1", "TTS for high+", priority_min="high", channel="tts")
        n_low = engine.send("Low", "low msg", priority="low")
        n_high = engine.send("High", "high msg", priority="high")
        assert n_low.channel == Channel.PUSH  # default, rule didn't match
        assert n_high.channel == Channel.TTS

    def test_quiet_hours(self, engine):
        engine.add_rule("r1", "Night quiet", quiet_hours_start=0, quiet_hours_end=24)
        n = engine.send("Test", "Should suppress", priority="normal")
        assert n.suppressed is True

    def test_quiet_hours_critical_override(self, engine):
        engine.add_rule("r1", "Night quiet", quiet_hours_start=0, quiet_hours_end=24)
        n = engine.send("Emergency", "Critical override", priority="critical")
        assert n.suppressed is False


# ── Read tracking ───────────────────────────────────────────────────────────


class TestReadTracking:
    def test_mark_read(self, engine):
        n = engine.send("Test", "msg")
        assert engine.mark_read(n.notification_id) is True
        history = engine.get_history(limit=1)
        assert history[0]["read"] is True

    def test_mark_read_unknown(self, engine):
        assert engine.mark_read("unknown") is False

    def test_mark_all_read(self, engine):
        engine.send("A", "a")
        engine.send("B", "b")
        count = engine.mark_all_read()
        assert count == 2
        assert all(n["read"] for n in engine.get_history())

    def test_unread_filter(self, engine):
        engine.send("A", "a")
        n2 = engine.send("B", "b")
        engine.mark_read(n2.notification_id)
        unread = engine.get_history(unread_only=True)
        assert len(unread) == 1
        assert unread[0]["title"] == "A"


# ── History ─────────────────────────────────────────────────────────────────


class TestHistory:
    def test_history_order(self, engine):
        engine.send("First", "1")
        engine.send("Second", "2")
        history = engine.get_history()
        assert history[0]["title"] == "Second"  # most recent first

    def test_history_limit(self, engine):
        for i in range(20):
            engine.send(f"N{i}", f"m{i}")
        history = engine.get_history(limit=5)
        assert len(history) == 5

    def test_history_category_filter(self, engine):
        engine.send("Sec", "s", category="security")
        engine.send("Info", "i", category="info")
        filtered = engine.get_history(category="security")
        assert len(filtered) == 1
        assert filtered[0]["category"] == "security"


# ── Stats ───────────────────────────────────────────────────────────────────


class TestStats:
    def test_stats_basic(self, engine):
        engine.send("A", "a", priority="high")
        engine.send("B", "b", priority="low")
        stats = engine.get_stats()
        assert isinstance(stats, NotificationStats)
        assert stats.total_sent == 2
        assert stats.by_priority["high"] == 1
        assert stats.by_priority["low"] == 1

    def test_stats_suppressed(self, engine):
        engine.set_dnd(enabled=True)
        engine.send("A", "a")
        stats = engine.get_stats()
        assert stats.total_suppressed == 1
        assert stats.total_sent == 0


# ── Dashboard ───────────────────────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_empty(self, engine):
        db = engine.get_dashboard()
        assert isinstance(db, NotificationIntelligenceDashboard)
        assert db.total_notifications == 0
        assert db.unread_count == 0

    def test_dashboard_with_data(self, engine):
        engine.send("A", "a")
        engine.send("B", "b")
        engine.add_rule("r1", "Rule", channel="tts")
        db = engine.get_dashboard()
        assert db.total_notifications == 2
        assert db.unread_count == 2
        assert db.rules_count == 1
        assert len(db.recent) == 2

    def test_dashboard_dnd_flag(self, engine):
        engine.set_dnd(enabled=True)
        db = engine.get_dashboard()
        assert db.dnd_active is True

    def test_dashboard_batch_pending(self, engine):
        engine.configure_batching(enabled=True)
        engine.send("A", "a")
        db = engine.get_dashboard()
        assert db.batch_pending == 1
