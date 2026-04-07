"""Tests for Brain Activity Engine (v7.5.0)."""

import pytest
import time
from copilot_core.hub.brain_activity import (
    BrainActivityEngine,
    BrainState,
    ChatMessage,
    ActivityPulse,
)


@pytest.fixture
def engine():
    return BrainActivityEngine(idle_timeout=2, sleep_timeout=10)


# ── State Tests ──────────────────────────────────────────────────────────────


class TestBrainState:
    def test_initial_state_idle(self, engine):
        assert engine.state == BrainState.IDLE

    def test_sleep(self, engine):
        result = engine.sleep()
        assert result == "sleeping"
        assert engine.state == BrainState.SLEEPING

    def test_wake_from_sleep(self, engine):
        engine.sleep()
        result = engine.wake()
        assert result == "idle"
        assert engine.state == BrainState.IDLE

    def test_wake_from_idle(self, engine):
        result = engine.wake()
        assert result == "idle"

    def test_sleep_ends_active_pulse(self, engine):
        engine.start_pulse("test")
        assert engine.state == BrainState.ACTIVE
        engine.sleep()
        assert engine.state == BrainState.SLEEPING
        assert len(engine._pulses) == 1


# ── Idle Check Tests ─────────────────────────────────────────────────────────


class TestIdleCheck:
    def test_check_idle_no_transition_if_active(self, engine):
        engine.start_pulse("test")
        result = engine.check_idle()
        assert result == "active"

    def test_check_idle_no_transition_if_recent(self, engine):
        engine.wake()
        result = engine.check_idle()
        assert result == "idle"

    def test_check_idle_transitions_to_sleep(self):
        engine = BrainActivityEngine(idle_timeout=0, sleep_timeout=10)
        engine.wake()
        result = engine.check_idle()
        assert result == "sleeping"

    def test_check_idle_sleeping_stays_sleeping(self, engine):
        engine.sleep()
        result = engine.check_idle()
        assert result == "sleeping"


# ── Pulse Tests ──────────────────────────────────────────────────────────────


class TestPulses:
    def test_start_pulse(self, engine):
        pulse = engine.start_pulse("chat")
        assert pulse.reason == "chat"
        assert pulse.started != ""
        assert engine.state == BrainState.ACTIVE

    def test_end_pulse(self, engine):
        engine.start_pulse("api_request")
        pulse = engine.end_pulse()
        assert pulse is not None
        assert pulse.ended != ""
        assert pulse.duration_ms >= 0
        assert engine.state == BrainState.IDLE

    def test_end_pulse_no_active(self, engine):
        assert engine.end_pulse() is None

    def test_pulse_counter(self, engine):
        engine.start_pulse("a")
        engine.end_pulse()
        engine.start_pulse("b")
        engine.end_pulse()
        assert len(engine._pulses) == 2

    def test_pulse_wakes_from_sleep(self, engine):
        engine.sleep()
        pulse = engine.start_pulse("wake_up")
        assert engine.state == BrainState.ACTIVE

    def test_recent_pulses(self, engine):
        for i in range(5):
            engine.start_pulse(f"test_{i}")
            engine.end_pulse()
        recent = engine.get_recent_pulses(3)
        assert len(recent) == 3
        assert recent[0].reason == "test_4"  # most recent first

    def test_pulse_history_capped(self):
        engine = BrainActivityEngine()
        for i in range(600):
            engine.start_pulse(f"test_{i}")
            engine.end_pulse()
        assert len(engine._pulses) == 500


# ── Chat Tests ───────────────────────────────────────────────────────────────


class TestChat:
    def test_add_user_message(self, engine):
        msg = engine.add_chat_message("user", "Hallo Styx!")
        assert msg.role == "user"
        assert msg.content == "Hallo Styx!"
        assert msg.timestamp != ""

    def test_add_assistant_message_auto_pulses(self, engine):
        engine.add_chat_message("assistant", "Hallo! Wie kann ich helfen?")
        assert len(engine._pulses) == 1
        assert engine._pulses[0].reason == "chat"

    def test_chat_history_order(self, engine):
        engine.add_chat_message("user", "Frage 1")
        engine.add_chat_message("assistant", "Antwort 1")
        engine.add_chat_message("user", "Frage 2")
        history = engine.get_chat_history(10)
        assert len(history) == 3
        assert history[0].content == "Frage 2"  # most recent first

    def test_chat_history_limit(self, engine):
        for i in range(10):
            engine.add_chat_message("user", f"Msg {i}")
        history = engine.get_chat_history(3)
        assert len(history) == 3

    def test_clear_chat_history(self, engine):
        engine.add_chat_message("user", "Test")
        engine.add_chat_message("assistant", "Reply")
        count = engine.clear_chat_history()
        assert count == 2
        assert len(engine.get_chat_history()) == 0

    def test_chat_wakes_from_sleep(self, engine):
        engine.sleep()
        engine.add_chat_message("user", "Wake up!")
        assert engine.state != BrainState.SLEEPING

    def test_chat_history_capped(self):
        engine = BrainActivityEngine()
        for i in range(250):
            engine.add_chat_message("user", f"msg_{i}")
        assert len(engine._chat_history) == 200

    def test_chat_message_metadata(self, engine):
        msg = engine.add_chat_message("user", "Test", {"source": "telegram"})
        assert msg.metadata["source"] == "telegram"


# ── Configuration Tests ──────────────────────────────────────────────────────


class TestConfiguration:
    def test_set_idle_timeout(self, engine):
        result = engine.set_idle_timeout(600)
        assert result == 600

    def test_set_idle_timeout_min(self, engine):
        result = engine.set_idle_timeout(5)
        assert result == 30  # clamped to 30

    def test_set_idle_timeout_max(self, engine):
        result = engine.set_idle_timeout(99999)
        assert result == 3600  # clamped to 3600

    def test_set_sleep_timeout(self, engine):
        result = engine.set_sleep_timeout(3600)
        assert result == 3600

    def test_set_sleep_timeout_min(self, engine):
        result = engine.set_sleep_timeout(10)
        assert result == 60

    def test_set_sleep_timeout_max(self, engine):
        result = engine.set_sleep_timeout(999999)
        assert result == 86400


# ── Status & Dashboard Tests ─────────────────────────────────────────────────


class TestStatus:
    def test_status_initial(self, engine):
        status = engine.get_status()
        assert status.state == "idle"
        assert status.total_pulses == 0
        assert status.total_chat_messages == 0
        assert status.uptime_seconds >= 0

    def test_status_after_activity(self, engine):
        engine.start_pulse("test")
        engine.end_pulse()
        engine.add_chat_message("user", "Hello")
        status = engine.get_status()
        assert status.total_pulses == 1
        assert status.total_chat_messages == 1
        assert status.last_active != ""

    def test_status_sleep_seconds(self, engine):
        engine.sleep()
        status = engine.get_status()
        assert status.state == "sleeping"
        assert status.sleep_seconds >= 0

    def test_dashboard(self, engine):
        engine.add_chat_message("user", "Test")
        engine.add_chat_message("assistant", "Reply")
        d = engine.get_dashboard()
        assert d["ok"]
        assert d["state"] == "idle"
        assert d["total_chat_messages"] == 2
        assert len(d["recent_chat"]) == 2
        assert len(d["recent_pulses"]) >= 1  # from assistant auto-pulse

    def test_dashboard_recent_chat_truncated(self, engine):
        engine.add_chat_message("user", "x" * 300)
        d = engine.get_dashboard()
        assert len(d["recent_chat"][0]["content"]) <= 200
