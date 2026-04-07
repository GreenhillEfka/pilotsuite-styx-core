"""Tests fuer das Alarm/Wecker-Modul.

Testet Models, Curves, Engine und API-Endpoints.
"""

import json
import math
import os
import tempfile
import time
from unittest.mock import MagicMock, Mock, patch

import pytest
from flask import Flask


# ============================================================================
# Models
# ============================================================================


class TestAlarmModels:
    """Tests fuer Alarm-Datenmodelle."""

    def test_alarm_mode_values(self):
        from copilot_core.alarm.models import AlarmMode
        assert AlarmMode.WAKE.value == "wake"
        assert AlarmMode.SLEEP.value == "sleep"

    def test_alarm_state_values(self):
        from copilot_core.alarm.models import AlarmState
        assert AlarmState.IDLE.value == "idle"
        assert AlarmState.ARMED.value == "armed"
        assert AlarmState.RUNNING.value == "running"
        assert AlarmState.SNOOZED.value == "snoozed"
        assert AlarmState.COMPLETED.value == "completed"
        assert AlarmState.CANCELLED.value == "cancelled"

    def test_curve_type_values(self):
        from copilot_core.alarm.models import CurveType
        assert CurveType.LINEAR.value == "linear"
        assert CurveType.QUADRATIC.value == "quadratic"
        assert CurveType.SIGMOID.value == "sigmoid"
        assert CurveType.PHILIPS_HUE.value == "philips_hue"
        assert CurveType.EXPONENTIAL.value == "exponential"

    def test_cct_to_rgb_exact(self):
        from copilot_core.alarm.models import cct_to_rgb
        assert cct_to_rgb(1800) == (255, 130, 46)
        assert cct_to_rgb(6500) == (248, 251, 255)

    def test_cct_to_rgb_interpolated(self):
        from copilot_core.alarm.models import cct_to_rgb
        r, g, b = cct_to_rgb(2100)
        assert 130 < g < 163  # Between 1800K and 2400K green values
        assert r == 255

    def test_cct_to_rgb_clamped(self):
        from copilot_core.alarm.models import cct_to_rgb
        assert cct_to_rgb(500) == (255, 130, 46)   # Clamped to 1800
        assert cct_to_rgb(9000) == (248, 251, 255)  # Clamped to 6500

    def test_alarm_schedule_defaults(self):
        from copilot_core.alarm.models import AlarmSchedule
        s = AlarmSchedule()
        assert s.time == "07:00"
        assert len(s.days) == 5
        assert s.enabled is True
        assert s.one_shot is False
        assert s.timezone == "Europe/Berlin"

    def test_light_config_defaults(self):
        from copilot_core.alarm.models import LightConfig
        lc = LightConfig()
        assert lc.duration_minutes == 30
        assert lc.brightness_start_pct == 0
        assert lc.brightness_end_pct == 100
        assert lc.cct_start_k == 1800
        assert lc.cct_end_k == 5000
        assert lc.step_interval_s == 10.0

    def test_light_config_total_steps(self):
        from copilot_core.alarm.models import LightConfig
        lc = LightConfig(duration_minutes=30, step_interval_s=10.0)
        assert lc.total_steps == 180  # 30*60/10

    def test_light_config_total_steps_zero_interval(self):
        from copilot_core.alarm.models import LightConfig
        lc = LightConfig(step_interval_s=0)
        assert lc.total_steps == 1

    def test_music_config_defaults(self):
        from copilot_core.alarm.models import MusicConfig
        mc = MusicConfig()
        assert mc.volume_start_pct == 5
        assert mc.volume_end_pct == 40
        assert mc.shuffle is True
        assert mc.enabled is True

    def test_alarm_config_to_dict(self):
        from copilot_core.alarm.models import AlarmConfig
        ac = AlarmConfig(alarm_id="test1", name="Morgen")
        d = ac.to_dict()
        assert d["alarm_id"] == "test1"
        assert d["name"] == "Morgen"
        assert "schedule" in d
        assert "light" in d
        assert "music" in d

    def test_alarm_config_from_dict(self):
        from copilot_core.alarm.models import AlarmConfig
        data = {
            "alarm_id": "abc",
            "name": "Testwecker",
            "mode": "sleep",
            "schedule": {"time": "22:30", "days": ["mon", "wed", "fri"]},
            "light": {"duration_minutes": 45, "curve_type": "sigmoid"},
            "music": {"volume_start_pct": 30, "volume_end_pct": 5},
            "snooze_minutes": 5,
        }
        ac = AlarmConfig.from_dict(data)
        assert ac.alarm_id == "abc"
        assert ac.mode == "sleep"
        assert ac.schedule.time == "22:30"
        assert ac.light.duration_minutes == 45
        assert ac.music.volume_start_pct == 30
        assert ac.snooze_minutes == 5

    def test_alarm_config_roundtrip(self):
        from copilot_core.alarm.models import AlarmConfig
        original = AlarmConfig(alarm_id="rt1", name="Roundtrip")
        data = original.to_dict()
        restored = AlarmConfig.from_dict(data)
        assert restored.to_dict() == data

    def test_alarm_runtime_to_dict(self):
        from copilot_core.alarm.models import AlarmRuntime
        rt = AlarmRuntime(state="running", progress_pct=45.67)
        d = rt.to_dict()
        assert d["state"] == "running"
        assert d["progress_pct"] == 45.7  # Rounded

    def test_alarm_preset_defaults(self):
        from copilot_core.alarm.models import AlarmPreset
        p = AlarmPreset(preset_id="p1", label="Test")
        assert p.mode == "wake"
        assert p.snooze_minutes == 9


# ============================================================================
# Curves
# ============================================================================


class TestAlarmCurves:
    """Tests fuer Helligkeits-Kurven."""

    def test_linear_boundaries(self):
        from copilot_core.alarm.curves import linear
        assert linear(0.0) == 0.0
        assert linear(1.0) == 1.0
        assert linear(0.5) == 0.5

    def test_linear_clamped(self):
        from copilot_core.alarm.curves import linear
        assert linear(-0.5) == 0.0
        assert linear(1.5) == 1.0

    def test_quadratic_boundaries(self):
        from copilot_core.alarm.curves import quadratic
        assert quadratic(0.0) == 0.0
        assert quadratic(1.0) == 1.0

    def test_quadratic_below_linear(self):
        from copilot_core.alarm.curves import quadratic
        # Quadratic should be below linear at t=0.5
        assert quadratic(0.5) == 0.25  # 0.5^2

    def test_sigmoid_boundaries(self):
        from copilot_core.alarm.curves import sigmoid
        assert abs(sigmoid(0.0)) < 0.01
        assert abs(sigmoid(1.0) - 1.0) < 0.01

    def test_sigmoid_midpoint(self):
        from copilot_core.alarm.curves import sigmoid
        # S-Kurve: Mitte sollte ca. 0.5 sein
        assert abs(sigmoid(0.5) - 0.5) < 0.05

    def test_sigmoid_s_shape(self):
        from copilot_core.alarm.curves import sigmoid
        # S-Kurve: langsamer Start, schnellere Mitte, langsames Ende
        v1 = sigmoid(0.2) - sigmoid(0.1)   # frueh: langsam
        v2 = sigmoid(0.5) - sigmoid(0.4)   # mitte: schnell
        v3 = sigmoid(0.9) - sigmoid(0.8)   # spaet: langsam
        assert v2 > v1
        assert v2 > v3

    def test_philips_hue_boundaries(self):
        from copilot_core.alarm.curves import philips_hue
        assert philips_hue(0.0) == 0.0
        assert abs(philips_hue(1.0) - 1.0) < 0.01

    def test_philips_hue_three_phases(self):
        from copilot_core.alarm.curves import philips_hue
        # Phase 1 Ende (t=0.3): sehr niedrig
        assert philips_hue(0.3) < 0.1
        # Phase 2 Ende (t=0.7): ca. 50%
        assert abs(philips_hue(0.7) - 0.5) < 0.05

    def test_exponential_boundaries(self):
        from copilot_core.alarm.curves import exponential
        assert abs(exponential(0.0)) < 0.01
        assert abs(exponential(1.0) - 1.0) < 0.01

    def test_exponential_slow_start(self):
        from copilot_core.alarm.curves import exponential
        # Exponential: erstes Drittel sollte < 10% sein
        assert exponential(0.33) < 0.15

    def test_get_curve_valid(self):
        from copilot_core.alarm.curves import get_curve
        fn = get_curve("sigmoid")
        assert callable(fn)
        assert abs(fn(0.5) - 0.5) < 0.1

    def test_get_curve_invalid_fallback(self):
        from copilot_core.alarm.curves import get_curve
        fn = get_curve("nonexistent")
        # Sollte auf quadratic fallen
        assert fn(0.5) == 0.25

    def test_reverse(self):
        from copilot_core.alarm.curves import linear, reverse
        rev = reverse(linear)
        # reversed linear(0) = 1 - linear(1) = 0
        assert abs(rev(0.0)) < 0.01
        # reversed linear(1) = 1 - linear(0) = 1
        assert abs(rev(1.0) - 1.0) < 0.01
        # Mitte bleibt gleich fuer linear
        assert abs(rev(0.5) - 0.5) < 0.01

    def test_reverse_quadratic(self):
        from copilot_core.alarm.curves import quadratic, reverse
        rev = reverse(quadratic)
        # Reversed: startet schnell, endet langsam (ideal fuer Sunset)
        v1 = rev(0.3) - rev(0.0)   # anfangs schnell
        v2 = rev(1.0) - rev(0.7)   # zum Ende langsam
        assert v1 > v2

    def test_interpolate_value(self):
        from copilot_core.alarm.curves import interpolate_value, linear
        assert interpolate_value(0, 100, 0.5, linear) == 50.0
        assert interpolate_value(10, 90, 0.0, linear) == 10.0
        assert interpolate_value(10, 90, 1.0, linear) == 90.0

    def test_interpolate_cct(self):
        from copilot_core.alarm.curves import interpolate_cct, linear
        assert interpolate_cct(1800, 5000, 0.5, linear) == 3400
        assert interpolate_cct(1800, 5000, 0.0, linear) == 1800
        assert interpolate_cct(1800, 5000, 1.0, linear) == 5000

    def test_philips_hue_phase_cct(self):
        from copilot_core.alarm.curves import philips_hue_phase_cct
        assert philips_hue_phase_cct(0.0) == 1800
        assert philips_hue_phase_cct(0.15) == 1800    # Phase 1: konstant 1800K
        assert philips_hue_phase_cct(0.5) == 2400      # Phase 2: zwischen 1800-3000K
        assert philips_hue_phase_cct(1.0) == 5000       # Phase 3 Ende

    def test_get_all_curves(self):
        from copilot_core.alarm.curves import get_all_curves
        curves = get_all_curves()
        assert len(curves) == 5
        for c in curves:
            assert "type" in c
            assert "description" in c
            assert "samples" in c
            assert len(c["samples"]) == 11
            # Erste Sample muss nahe 0, letzte nahe 1 sein
            assert c["samples"][0] < 0.1
            assert c["samples"][-1] > 0.9

    def test_all_curves_monotonic(self):
        """Alle Kurven muessen monoton steigend sein."""
        from copilot_core.alarm.curves import get_all_curves
        for curve in get_all_curves():
            samples = curve["samples"]
            for i in range(1, len(samples)):
                assert samples[i] >= samples[i - 1] - 0.001, \
                    f"{curve['type']}: nicht monoton bei index {i}"


# ============================================================================
# Engine
# ============================================================================


class TestAlarmEngine:
    """Tests fuer die AlarmEngine."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.configs_dir = str(tmp_path / "configs")
        self.presets_dir = str(tmp_path / "presets")
        self.mock_sonos = MagicMock()
        self.engine = self._create_engine()

    def _create_engine(self):
        from copilot_core.alarm.engine import AlarmEngine
        return AlarmEngine(
            sonos_client=self.mock_sonos,
            configs_dir=self.configs_dir,
            presets_dir=self.presets_dir,
        )

    def test_create_alarm(self):
        config = self.engine.create_alarm({
            "name": "Testwecker",
            "mode": "wake",
            "schedule": {"time": "07:00"},
        })
        assert config.name == "Testwecker"
        assert config.alarm_id != ""

    def test_create_alarm_with_id(self):
        config = self.engine.create_alarm({
            "alarm_id": "myalarm",
            "name": "Mein Wecker",
        })
        assert config.alarm_id == "myalarm"

    def test_list_alarms(self):
        self.engine.create_alarm({"name": "W1"})
        self.engine.create_alarm({"name": "W2"})
        alarms = self.engine.list_alarms()
        assert len(alarms) == 2

    def test_get_alarm(self):
        config = self.engine.create_alarm({"name": "Get-Test", "alarm_id": "get1"})
        result = self.engine.get_alarm("get1")
        assert result is not None
        assert result["name"] == "Get-Test"
        assert "runtime" in result

    def test_get_alarm_not_found(self):
        assert self.engine.get_alarm("nope") is None

    def test_update_alarm(self):
        self.engine.create_alarm({"alarm_id": "upd1", "name": "Original"})
        updated = self.engine.update_alarm("upd1", {
            "name": "Updated",
            "schedule": {"time": "08:00"},
        })
        assert updated is not None
        assert updated.name == "Updated"
        assert updated.schedule.time == "08:00"

    def test_update_alarm_not_found(self):
        assert self.engine.update_alarm("nope", {}) is None

    def test_delete_alarm(self):
        self.engine.create_alarm({"alarm_id": "del1"})
        assert self.engine.delete_alarm("del1") is True
        assert self.engine.get_alarm("del1") is None

    def test_delete_alarm_not_found(self):
        assert self.engine.delete_alarm("nope") is False

    def test_get_alarms_for_zone(self):
        self.engine.create_alarm({"alarm_id": "z1", "zone_id": "wohnzimmer"})
        self.engine.create_alarm({"alarm_id": "z2", "zone_id": "schlafzimmer"})
        self.engine.create_alarm({"alarm_id": "z3", "zone_id": "wohnzimmer"})
        zone_alarms = self.engine.get_alarms_for_zone("wohnzimmer")
        assert len(zone_alarms) == 2

    def test_persistence(self):
        self.engine.create_alarm({"alarm_id": "persist1", "name": "Persist"})
        # Neue Engine mit gleichen Verzeichnissen
        engine2 = self._create_engine()
        alarm = engine2.get_alarm("persist1")
        assert alarm is not None
        assert alarm["name"] == "Persist"

    def test_trigger_alarm(self):
        self.engine.create_alarm({"alarm_id": "trig1"})
        result = self.engine.trigger_alarm("trig1")
        assert result is not None
        assert result["action"] == "triggered"
        # Kurz warten damit Thread startet
        time.sleep(0.1)
        alarm = self.engine.get_alarm("trig1")
        assert alarm["runtime"]["state"] == "running"

    def test_trigger_alarm_not_found(self):
        assert self.engine.trigger_alarm("nope") is None

    def test_cancel_alarm(self):
        self.engine.create_alarm({"alarm_id": "canc1"})
        self.engine.trigger_alarm("canc1")
        time.sleep(0.1)
        result = self.engine.cancel_alarm("canc1")
        assert result is not None
        assert result["action"] == "cancelled"

    def test_snooze_alarm(self):
        self.engine.create_alarm({
            "alarm_id": "snz1",
            "snooze_minutes": 1,
            "light": {"step_interval_s": 1, "duration_minutes": 1},
        })
        self.engine.trigger_alarm("snz1")
        time.sleep(0.2)
        result = self.engine.snooze_alarm("snz1")
        assert result is not None
        assert result["action"] == "snoozed"
        assert result["snooze_count"] == 1

    def test_snooze_alarm_not_running(self):
        self.engine.create_alarm({"alarm_id": "snz2"})
        result = self.engine.snooze_alarm("snz2")
        assert result is not None
        assert result["action"] == "not_running"

    def test_default_presets_installed(self):
        presets = self.engine.list_presets()
        assert len(presets) >= 5
        labels = [p["label"] for p in presets]
        assert "Sanfter Sonnenaufgang" in labels
        assert "Sanfter Sonnenuntergang" in labels

    def test_preset_get(self):
        preset = self.engine.get_preset("sunrise_gentle")
        assert preset is not None
        assert preset["mode"] == "wake"

    def test_preset_delete(self):
        assert self.engine.delete_preset("sunrise_gentle") is True
        assert self.engine.get_preset("sunrise_gentle") is None

    def test_create_from_preset(self):
        config = self.engine.create_from_preset("sunrise_gentle", {
            "schedule": {"time": "06:30"},
            "zone_id": "schlafzimmer",
        })
        assert config is not None
        assert config.zone_id == "schlafzimmer"

    def test_create_from_preset_not_found(self):
        assert self.engine.create_from_preset("nope") is None

    def test_dashboard(self):
        self.engine.create_alarm({"alarm_id": "dash1"})
        dashboard = self.engine.get_dashboard()
        assert "alarms" in dashboard
        assert "presets" in dashboard
        assert "curves" in dashboard
        assert dashboard["total_count"] == 1

    @patch("copilot_core.alarm.engine.requests.post")
    def test_ha_light_control(self, mock_post):
        """Testet dass light.turn_on via Supervisor API aufgerufen wird."""
        mock_post.return_value = Mock(status_code=200)
        self.engine.create_alarm({
            "alarm_id": "light1",
            "light": {
                "entity_ids": ["light.schlafzimmer"],
                "duration_minutes": 1,
                "step_interval_s": 0.05,
            },
        })
        self.engine.trigger_alarm("light1")
        time.sleep(0.5)
        self.engine.cancel_alarm("light1")
        # Mindestens ein light.turn_on Call
        assert mock_post.call_count >= 1

    def test_sonos_music_start(self):
        """Testet Sonos-Musikstart bei Alarm."""
        self.engine.create_alarm({
            "alarm_id": "mus1",
            "music": {
                "source_type": "favorite",
                "source_name": "Morning Jazz",
                "sonos_room": "Schlafzimmer",
                "volume_start_pct": 10,
                "enabled": True,
            },
            "light": {"duration_minutes": 1, "step_interval_s": 0.05},
        })
        self.engine.trigger_alarm("mus1")
        time.sleep(0.3)
        self.engine.cancel_alarm("mus1")
        self.mock_sonos.play_favorite.assert_called()
        self.mock_sonos.set_volume.assert_called()

    def test_scheduler_start_stop(self):
        self.engine.start()
        assert self.engine._scheduler_thread is not None
        assert self.engine._scheduler_thread.is_alive()
        self.engine.stop()
        time.sleep(0.2)
        assert not self.engine._scheduler_thread or not self.engine._scheduler_thread.is_alive()

    def test_scheduler_double_start(self):
        self.engine.start()
        t1 = self.engine._scheduler_thread
        self.engine.start()  # Zweiter Start — gleicher Thread
        assert self.engine._scheduler_thread is t1
        self.engine.stop()


# ============================================================================
# API Endpoints
# ============================================================================


def _make_test_app():
    """Erstellt Test-App mit Alarm-Blueprint."""
    from copilot_core.api.v1.alarm import alarm_bp, init_alarm_api
    from copilot_core.alarm.engine import AlarmEngine

    mock_sonos = MagicMock()
    tmpdir = tempfile.mkdtemp()
    engine = AlarmEngine(
        sonos_client=mock_sonos,
        configs_dir=os.path.join(tmpdir, "configs"),
        presets_dir=os.path.join(tmpdir, "presets"),
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    init_alarm_api(engine)

    # Blueprint-Registry zuruecksetzen falls noetig
    if "alarm" in app.blueprints:
        del app.blueprints["alarm"]

    with patch("copilot_core.api.v1.alarm.require_token", lambda f: f):
        # Blueprint neu importieren mit gepatchtem Decorator
        import importlib
        import copilot_core.api.v1.alarm as alarm_mod
        importlib.reload(alarm_mod)
        alarm_mod.init_alarm_api(engine)
        app.register_blueprint(alarm_mod.alarm_bp)

    return app, engine, mock_sonos


class TestAlarmAPI:
    """Tests fuer Alarm REST API Endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app, self.engine, self.mock_sonos = _make_test_app()
        try:
            from copilot_core.api.rate_limit import get_rate_limiter
            get_rate_limiter().reset()
        except Exception:
            pass

    def _client(self):
        return self.app.test_client()

    def test_dashboard(self):
        with self._client() as c:
            resp = c.get("/api/v1/alarm/dashboard")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert "alarms" in data
            assert "presets" in data
            assert "curves" in data

    def test_list_alarms_empty(self):
        with self._client() as c:
            resp = c.get("/api/v1/alarm/alarms")
            assert resp.status_code == 200
            assert resp.get_json()["alarms"] == []

    def test_create_alarm(self):
        with self._client() as c:
            resp = c.post("/api/v1/alarm/alarms", json={
                "name": "API-Wecker",
                "schedule": {"time": "07:30"},
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["ok"] is True
            assert data["alarm"]["name"] == "API-Wecker"

    def test_get_alarm(self):
        self.engine.create_alarm({"alarm_id": "api1", "name": "API-Get"})
        with self._client() as c:
            resp = c.get("/api/v1/alarm/alarms/api1")
            assert resp.status_code == 200
            assert resp.get_json()["alarm"]["name"] == "API-Get"

    def test_get_alarm_not_found(self):
        with self._client() as c:
            resp = c.get("/api/v1/alarm/alarms/nope")
            assert resp.status_code == 404

    def test_update_alarm(self):
        self.engine.create_alarm({"alarm_id": "upd1", "name": "Original"})
        with self._client() as c:
            resp = c.put("/api/v1/alarm/alarms/upd1", json={
                "name": "Updated",
            })
            assert resp.status_code == 200
            assert resp.get_json()["alarm"]["name"] == "Updated"

    def test_update_alarm_not_found(self):
        with self._client() as c:
            resp = c.put("/api/v1/alarm/alarms/nope", json={"name": "X"})
            assert resp.status_code == 404

    def test_delete_alarm(self):
        self.engine.create_alarm({"alarm_id": "del1"})
        with self._client() as c:
            resp = c.delete("/api/v1/alarm/alarms/del1")
            assert resp.status_code == 200
            assert resp.get_json()["deleted"] == "del1"

    def test_delete_alarm_not_found(self):
        with self._client() as c:
            resp = c.delete("/api/v1/alarm/alarms/nope")
            assert resp.status_code == 404

    def test_trigger_alarm(self):
        self.engine.create_alarm({"alarm_id": "trig1"})
        with self._client() as c:
            resp = c.post("/api/v1/alarm/alarms/trig1/trigger")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["action"] == "triggered"
        self.engine.cancel_alarm("trig1")

    def test_trigger_alarm_not_found(self):
        with self._client() as c:
            resp = c.post("/api/v1/alarm/alarms/nope/trigger")
            assert resp.status_code == 404

    def test_snooze_alarm(self):
        self.engine.create_alarm({
            "alarm_id": "snz1",
            "snooze_minutes": 1,
            "light": {"step_interval_s": 1, "duration_minutes": 1},
        })
        self.engine.trigger_alarm("snz1")
        time.sleep(0.1)
        with self._client() as c:
            resp = c.post("/api/v1/alarm/alarms/snz1/snooze")
            assert resp.status_code == 200
            assert resp.get_json()["action"] == "snoozed"
        self.engine.cancel_alarm("snz1")

    def test_cancel_alarm(self):
        self.engine.create_alarm({"alarm_id": "canc1"})
        self.engine.trigger_alarm("canc1")
        time.sleep(0.1)
        with self._client() as c:
            resp = c.post("/api/v1/alarm/alarms/canc1/cancel")
            assert resp.status_code == 200
            assert resp.get_json()["action"] == "cancelled"

    def test_zone_alarms(self):
        self.engine.create_alarm({"alarm_id": "za1", "zone_id": "wohnzimmer"})
        self.engine.create_alarm({"alarm_id": "za2", "zone_id": "schlafzimmer"})
        with self._client() as c:
            resp = c.get("/api/v1/alarm/zones/wohnzimmer/alarms")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["alarms"]) == 1
            assert data["zone_id"] == "wohnzimmer"

    def test_presets_list(self):
        with self._client() as c:
            resp = c.get("/api/v1/alarm/presets")
            assert resp.status_code == 200
            presets = resp.get_json()["presets"]
            assert len(presets) >= 5

    def test_preset_get(self):
        with self._client() as c:
            resp = c.get("/api/v1/alarm/presets/sunrise_gentle")
            assert resp.status_code == 200
            assert resp.get_json()["preset"]["mode"] == "wake"

    def test_preset_get_not_found(self):
        with self._client() as c:
            resp = c.get("/api/v1/alarm/presets/nope")
            assert resp.status_code == 404

    def test_preset_delete(self):
        with self._client() as c:
            resp = c.delete("/api/v1/alarm/presets/sunrise_gentle")
            assert resp.status_code == 200

    def test_create_from_preset(self):
        with self._client() as c:
            resp = c.post("/api/v1/alarm/presets/sunrise_philips/create-alarm", json={
                "schedule": {"time": "06:00"},
                "zone_id": "schlafzimmer",
            })
            assert resp.status_code == 201
            assert resp.get_json()["ok"] is True

    def test_create_from_preset_not_found(self):
        with self._client() as c:
            resp = c.post("/api/v1/alarm/presets/nope/create-alarm", json={})
            assert resp.status_code == 404

    def test_curves(self):
        with self._client() as c:
            resp = c.get("/api/v1/alarm/curves")
            assert resp.status_code == 200
            curves = resp.get_json()["curves"]
            assert len(curves) == 5
            types = [c["type"] for c in curves]
            assert "quadratic" in types
            assert "sigmoid" in types


class TestAlarmAPINoEngine:
    """Tests ohne initialisierte Engine (503-Checks)."""

    def test_503_when_no_engine(self):
        from copilot_core.api.v1.alarm import alarm_bp, init_alarm_api
        import importlib
        import copilot_core.api.v1.alarm as alarm_mod

        with patch("copilot_core.api.v1.alarm.require_token", lambda f: f):
            importlib.reload(alarm_mod)
            alarm_mod.init_alarm_api(None)
            app = Flask(__name__)
            app.config["TESTING"] = True
            app.register_blueprint(alarm_mod.alarm_bp)

            with app.test_client() as c:
                resp = c.get("/api/v1/alarm/dashboard")
                assert resp.status_code == 503
                resp = c.get("/api/v1/alarm/alarms")
                assert resp.status_code == 503
