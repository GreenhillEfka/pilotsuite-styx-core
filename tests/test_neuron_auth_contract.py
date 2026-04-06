"""Neuron/Auth + Sonnenwecker-Integration Tests (legacy contract).

Enthält aktuell die für diese Task relevanten Regressionstests. Weitere
Auth-Verifikationen liegen in den dedizierten Testdateien im selben Bundle.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../copilot_core/rootfs/usr/src/app'))

from copilot_core.neurons.neuron_auth import (
    NeuronCapability,
    NeuronPermission,
    RolePermissions,
    check_neuron_capability,
    require_neuron_capability,
    get_role_permissions,
    get_auth_diagnosis,
    guard_neuron_read,
    guard_neuron_override,
)

from copilot_core.modules.sonnenwecker.engine import SunlightAlarmConfig, get_sonnenwecker_engine
from copilot_core.modules.music_wolke.engine import MusicWolkeEngine


class TestNeuronAuthContracts:
    """Smoke-Checks für die bestehenden Auth-Verträge."""

    def test_module_role_can_execute(self):
        rp = get_role_permissions("module")
        assert rp.has_capability("*", NeuronCapability.EXECUTE)

    def test_admin_can_override_any_neuron(self):
        assert check_neuron_capability("admin", "presence_intent", NeuronCapability.OVERRIDE)

    def test_require_capability_raises_on_bad_input(self):
        with pytest.raises(PermissionError):
            require_neuron_capability("user", "brain_graph", NeuronCapability.OVERRIDE)


class TestSonnenweckerMusicWolkeSeparation:
    """Sonnenwecker <-> Musikwolke Abhängigkeit und Schlaf-Interaktion."""

    def test_sonnenwecker_config_includes_sleep_suppression_flag(self):
        engine = get_sonnenwecker_engine()
        cfg = SunlightAlarmConfig(
            enabled=True,
            music_on_wake=True,
            music_volume_start=0.15,
            suppress_music_cloud_during_sleep=False,
        )
        engine.configure("zone.bedroom", cfg)
        config = engine.get_config("zone.bedroom")
        assert config is not None
        assert config.suppress_music_cloud_during_sleep is False

    def test_sonnenwecker_on_sleep_stops_music(self):
        """Sleep-Status stoppt Musikwolke mit Fade-Out."""
        sw = get_sonnenwecker_engine()
        mw = MusicWolkeEngine.get_instance()

        cfg = SunlightAlarmConfig(enabled=True, music_on_wake=False)
        sw.configure("zone.bedroom", cfg)

        sid = mw.start_session(
            zone_id="zone.bedroom",
            source_entity="sonos.bedroom",
            media_type="music",
            follow_enabled=False,
            volume_pct=42,
        )
        assert sid is not None

        triggered = sw.on_sleep_detected("zone.bedroom")
        assert any("music_stopped:" in t or "alarm_cancelled" in t for t in triggered)

        # Fade-Out läuft asynchron -> warten, bis Stop eingetreten ist.
        for _ in range(12):
            if mw.get_session(sid) is None:
                break
            time.sleep(0.5)
        assert mw.get_session(sid) is None

    def test_sonnenwecker_sleep_lock_can_be_disabled(self):
        """Suppression ist konfigurierbar; bei False bleibt Session aktiv."""
        sw = get_sonnenwecker_engine()
        mw = MusicWolkeEngine.get_instance()

        cfg = SunlightAlarmConfig(
            enabled=True,
            music_on_wake=False,
            suppress_music_cloud_during_sleep=False,
        )
        sw.configure("zone.living", cfg)

        sid = mw.start_session(
            zone_id="zone.living",
            source_entity="sonos.living",
            media_type="music",
            follow_enabled=False,
            volume_pct=35,
        )
        assert sid is not None

        triggered = sw.on_sleep_detected("zone.living")
        assert not any(t.startswith("music_stopped:") for t in triggered)

        assert mw.get_session(sid) is not None
        mw.stop_session(sid)

    def test_guard_can_read_without_override(self):
        """Auth-Guard bleibt unangetastet."""
        assert require_neuron_capability("admin", "brain_graph", NeuronCapability.READ)
        with pytest.raises(PermissionError):
            require_neuron_capability("user", "brain_graph", NeuronCapability.DISABLE)
