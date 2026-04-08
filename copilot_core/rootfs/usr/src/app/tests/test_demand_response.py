"""Tests for Demand Response Manager (v5.14.0)."""

import pytest
from copilot_core.energy.demand_response import (
    DemandResponseManager,
    DemandResponseStatus,
    SignalLevel,
    DevicePriority,
    ManagedDevice,
    GridSignal,
    CurtailmentAction,
)


@pytest.fixture
def mgr():
    return DemandResponseManager()


@pytest.fixture
def mgr_with_devices(mgr):
    """Manager with sample devices registered."""
    mgr.register_device("pool_pump", "Pool Pumpe", DevicePriority.DEFERRABLE, 1500)
    mgr.register_device("ev_charger", "EV Ladestation", DevicePriority.FLEXIBLE, 7400)
    mgr.register_device("heat_pump", "Waermepumpe", DevicePriority.COMFORT, 3000)
    mgr.register_device("fridge", "Kuehlschrank", DevicePriority.ESSENTIAL, 150)
    return mgr


# ═══════════════════════════════════════════════════════════════════════════
# Device Registration
# ═══════════════════════════════════════════════════════════════════════════


class TestDeviceRegistration:
    def test_register_device(self, mgr):
        dev = mgr.register_device("pump", "Pool Pumpe", DevicePriority.DEFERRABLE, 1500)
        assert isinstance(dev, ManagedDevice)
        assert dev.device_id == "pump"

    def test_list_devices(self, mgr_with_devices):
        devices = mgr_with_devices.get_devices()
        assert len(devices) == 4

    def test_unregister_device(self, mgr_with_devices):
        result = mgr_with_devices.unregister_device("pool_pump")
        assert result is True
        assert len(mgr_with_devices.get_devices()) == 3

    def test_unregister_nonexistent(self, mgr):
        assert mgr.unregister_device("nope") is False

    def test_update_power(self, mgr_with_devices):
        result = mgr_with_devices.update_device_power("ev_charger", 5000)
        assert result is True

    def test_update_power_nonexistent(self, mgr):
        assert mgr.update_device_power("nope", 100) is False

    def test_device_priority(self, mgr):
        dev = mgr.register_device("d1", "D1", DevicePriority.ESSENTIAL, 100)
        assert dev.priority == DevicePriority.ESSENTIAL


# ═══════════════════════════════════════════════════════════════════════════
# Signal Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestSignalHandling:
    def test_receive_signal(self, mgr):
        sig = mgr.receive_signal(SignalLevel.ADVISORY, "grid_operator", "Peak warning")
        assert isinstance(sig, GridSignal)
        assert sig.level == SignalLevel.ADVISORY

    def test_active_signals(self, mgr):
        mgr.receive_signal(SignalLevel.MODERATE, "grid", "Test")
        signals = mgr.get_active_signals()
        assert len(signals) >= 1

    def test_cancel_signal(self, mgr):
        sig = mgr.receive_signal(SignalLevel.ADVISORY, "grid", "Test")
        result = mgr.cancel_signal(sig.signal_id)
        assert result is True

    def test_cancel_nonexistent(self, mgr):
        assert mgr.cancel_signal("nope") is False

    def test_signal_has_expiry(self, mgr):
        sig = mgr.receive_signal(SignalLevel.MODERATE, "grid", "Test", duration_minutes=30)
        assert sig.expires_at > sig.received_at


# ═══════════════════════════════════════════════════════════════════════════
# Auto-Curtailment
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoCurtailment:
    def test_moderate_sheds_deferrable(self, mgr_with_devices):
        mgr_with_devices.receive_signal(SignalLevel.MODERATE, "grid", "Peak demand")
        curtailed = mgr_with_devices.get_curtailed_devices()
        ids = {d["device_id"] for d in curtailed}
        assert "pool_pump" in ids  # DEFERRABLE
        assert "ev_charger" in ids  # FLEXIBLE

    def test_moderate_spares_comfort(self, mgr_with_devices):
        mgr_with_devices.receive_signal(SignalLevel.MODERATE, "grid", "Peak demand")
        curtailed = mgr_with_devices.get_curtailed_devices()
        ids = {d["device_id"] for d in curtailed}
        assert "heat_pump" not in ids  # COMFORT — spared at MODERATE

    def test_critical_sheds_comfort(self, mgr_with_devices):
        mgr_with_devices.receive_signal(SignalLevel.CRITICAL, "grid", "Grid emergency")
        curtailed = mgr_with_devices.get_curtailed_devices()
        ids = {d["device_id"] for d in curtailed}
        assert "heat_pump" in ids  # COMFORT shed at CRITICAL

    def test_never_sheds_essential(self, mgr_with_devices):
        mgr_with_devices.receive_signal(SignalLevel.CRITICAL, "grid", "Emergency")
        curtailed = mgr_with_devices.get_curtailed_devices()
        ids = {d["device_id"] for d in curtailed}
        assert "fridge" not in ids  # ESSENTIAL never shed

    def test_advisory_no_auto_curtail(self, mgr_with_devices):
        mgr_with_devices.receive_signal(SignalLevel.ADVISORY, "grid", "Info")
        curtailed = mgr_with_devices.get_curtailed_devices()
        assert len(curtailed) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Manual Curtailment
# ═══════════════════════════════════════════════════════════════════════════


class TestManualCurtailment:
    def test_curtail_device(self, mgr_with_devices):
        action = mgr_with_devices.curtail_device("pool_pump")
        assert isinstance(action, CurtailmentAction)
        assert action.action == "curtail"

    def test_curtail_already_curtailed(self, mgr_with_devices):
        mgr_with_devices.curtail_device("pool_pump")
        action = mgr_with_devices.curtail_device("pool_pump")
        assert action is None

    def test_curtail_nonexistent(self, mgr):
        action = mgr.curtail_device("nope")
        assert action is None

    def test_restore_device(self, mgr_with_devices):
        mgr_with_devices.curtail_device("pool_pump")
        action = mgr_with_devices.restore_device("pool_pump")
        assert action is not None
        assert action.action == "restore"

    def test_restore_not_curtailed(self, mgr_with_devices):
        action = mgr_with_devices.restore_device("pool_pump")
        assert action is None


# ═══════════════════════════════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════════════════════════════


class TestStatus:
    def test_initial_status(self, mgr):
        s = mgr.get_status()
        assert isinstance(s, DemandResponseStatus)
        assert s.current_signal == 0
        assert s.response_active is False

    def test_status_with_signal(self, mgr_with_devices):
        mgr_with_devices.receive_signal(SignalLevel.MODERATE, "grid", "Test")
        s = mgr_with_devices.get_status()
        assert s.current_signal == SignalLevel.MODERATE
        assert s.active_signals >= 1
        assert s.response_active is True

    def test_curtailed_count(self, mgr_with_devices):
        mgr_with_devices.curtail_device("pool_pump")
        s = mgr_with_devices.get_status()
        assert s.curtailed_devices == 1

    def test_total_reduction(self, mgr_with_devices):
        mgr_with_devices.curtail_device("ev_charger")
        s = mgr_with_devices.get_status()
        assert s.total_reduction_watts > 0

    def test_managed_devices_count(self, mgr_with_devices):
        s = mgr_with_devices.get_status()
        assert s.managed_devices == 4


# ═══════════════════════════════════════════════════════════════════════════
# History & Metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestHistoryMetrics:
    def test_action_history(self, mgr_with_devices):
        mgr_with_devices.curtail_device("pool_pump")
        mgr_with_devices.restore_device("pool_pump")
        history = mgr_with_devices.get_action_history()
        assert len(history) == 2

    def test_history_most_recent_first(self, mgr_with_devices):
        mgr_with_devices.curtail_device("pool_pump")
        mgr_with_devices.curtail_device("ev_charger")
        history = mgr_with_devices.get_action_history()
        assert history[0]["device_id"] == "ev_charger"

    def test_history_limit(self, mgr_with_devices):
        mgr_with_devices.curtail_device("pool_pump")
        mgr_with_devices.curtail_device("ev_charger")
        mgr_with_devices.curtail_device("heat_pump")
        history = mgr_with_devices.get_action_history(limit=2)
        assert len(history) == 2

    def test_metrics(self, mgr_with_devices):
        mgr_with_devices.curtail_device("pool_pump")
        mgr_with_devices.restore_device("pool_pump")
        m = mgr_with_devices.get_metrics()
        assert m["total_actions"] == 2
        assert m["curtail_actions"] == 1
        assert m["restore_actions"] == 1

    def test_metrics_empty(self, mgr):
        m = mgr.get_metrics()
        assert m["total_actions"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Signal Cancellation & Restore
# ═══════════════════════════════════════════════════════════════════════════


class TestSignalCancellation:
    def test_cancel_restores_devices(self, mgr_with_devices):
        sig = mgr_with_devices.receive_signal(SignalLevel.MODERATE, "grid", "Test")
        # Should have curtailed pool_pump and ev_charger
        assert len(mgr_with_devices.get_curtailed_devices()) > 0

        mgr_with_devices.cancel_signal(sig.signal_id)
        assert len(mgr_with_devices.get_curtailed_devices()) == 0

    def test_cancel_creates_restore_actions(self, mgr_with_devices):
        sig = mgr_with_devices.receive_signal(SignalLevel.MODERATE, "grid", "Test")
        mgr_with_devices.cancel_signal(sig.signal_id)

        history = mgr_with_devices.get_action_history()
        restore_actions = [a for a in history if a["action"] == "restore"]
        assert len(restore_actions) >= 2
