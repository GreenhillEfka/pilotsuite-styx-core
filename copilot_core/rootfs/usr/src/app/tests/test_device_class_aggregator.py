"""Tests for device_class_aggregator — Sammelentitaeten per zone."""

import pytest

from copilot_core.homeassistant.device_class_aggregator import (
    AGGREGATE_CATEGORIES,
    AggregateEntity,
    AggregateResult,
    CategoryDef,
    ZoneAggregator,
    _compute_status,
    _compute_summary,
    _safe_float,
    _summarize_climate,
    _summarize_covers,
    _summarize_lights,
    _summarize_media,
    _summarize_motion,
    _summarize_numeric,
    _summarize_power,
    _summarize_security,
)


class TestCategoryDefs:
    def test_all_categories_present(self):
        ids = {c.category_id for c in AGGREGATE_CATEGORIES}
        expected = {
            "beleuchtung", "temperatur", "heizung", "luftfeuchte",
            "luftqualitaet", "medien", "rollladen", "strom",
            "bewegung", "sicherheit", "batterie",
        }
        assert ids == expected

    def test_categories_are_frozen(self):
        for cat in AGGREGATE_CATEGORIES:
            assert isinstance(cat, CategoryDef)
            with pytest.raises(AttributeError):
                cat.name_de = "changed"

    def test_each_has_icon(self):
        for cat in AGGREGATE_CATEGORIES:
            assert cat.icon.startswith("mdi:")

    def test_each_has_domains(self):
        for cat in AGGREGATE_CATEGORIES:
            assert len(cat.domains) > 0


class TestSafeFloat:
    def test_valid_float(self):
        assert _safe_float("21.5") == 21.5

    def test_valid_int(self):
        assert _safe_float("42") == 42.0

    def test_none(self):
        assert _safe_float(None) is None

    def test_unknown(self):
        assert _safe_float("unknown") is None

    def test_unavailable(self):
        assert _safe_float("unavailable") is None

    def test_empty(self):
        assert _safe_float("") is None

    def test_non_numeric(self):
        assert _safe_float("abc") is None


class TestSummarizeLights:
    def _make_light(self, state="on", brightness=None, color_temp_k=None):
        attrs = {}
        if brightness is not None:
            attrs["brightness"] = brightness
        if color_temp_k is not None:
            attrs["color_temp_kelvin"] = color_temp_k
        return AggregateEntity(
            entity_id=f"light.test_{id(state)}",
            friendly_name="Test Light",
            state=state,
            attributes=attrs,
        )

    def test_all_on(self):
        entities = [self._make_light("on", 200), self._make_light("on", 100)]
        s = _summarize_lights(entities)
        assert s["on_count"] == 2
        assert s["off_count"] == 0
        assert s["all_on"] is True
        assert s["all_off"] is False
        assert s["avg_brightness_pct"] > 0

    def test_all_off(self):
        entities = [self._make_light("off"), self._make_light("off")]
        s = _summarize_lights(entities)
        assert s["on_count"] == 0
        assert s["all_off"] is True
        assert s["avg_brightness_pct"] == 0

    def test_mixed(self):
        entities = [self._make_light("on", 255), self._make_light("off")]
        s = _summarize_lights(entities)
        assert s["on_count"] == 1
        assert s["off_count"] == 1

    def test_color_temp(self):
        entities = [self._make_light("on", 200, 2700), self._make_light("on", 200, 3300)]
        s = _summarize_lights(entities)
        assert s["avg_color_temp_k"] == 3000


class TestSummarizeNumeric:
    def test_multiple_values(self):
        entities = [
            AggregateEntity(entity_id="sensor.t1", friendly_name="T1", state="21.5"),
            AggregateEntity(entity_id="sensor.t2", friendly_name="T2", state="22.5"),
            AggregateEntity(entity_id="sensor.t3", friendly_name="T3", state="20.0"),
        ]
        s = _summarize_numeric(entities, "°C")
        assert s["available"] is True
        assert s["avg"] == pytest.approx(21.3, abs=0.1)
        assert s["min"] == 20.0
        assert s["max"] == 22.5
        assert s["sensor_count"] == 3

    def test_no_valid_values(self):
        entities = [
            AggregateEntity(entity_id="sensor.t1", friendly_name="T1", state="unavailable"),
        ]
        s = _summarize_numeric(entities, "°C")
        assert s["available"] is False


class TestSummarizeClimate:
    def test_heating(self):
        entities = [
            AggregateEntity(
                entity_id="climate.hz1", friendly_name="Heizung 1", state="heat",
                attributes={"current_temperature": 20.5, "temperature": 22.0, "hvac_mode": "heat"},
            ),
            AggregateEntity(
                entity_id="climate.hz2", friendly_name="Heizung 2", state="auto",
                attributes={"current_temperature": 21.0, "temperature": 21.5, "hvac_mode": "auto"},
            ),
        ]
        s = _summarize_climate(entities)
        assert s["heating_count"] == 2
        assert s["avg_current_temp"] == pytest.approx(20.75, abs=0.1)
        assert s["avg_target_temp"] == pytest.approx(21.75, abs=0.1)
        assert s["all_off"] is False


class TestSummarizeMedia:
    def test_playing(self):
        entities = [
            AggregateEntity(
                entity_id="media_player.tv", friendly_name="TV", state="playing",
                attributes={"media_title": "Test Movie", "media_artist": "Director"},
            ),
            AggregateEntity(
                entity_id="media_player.sonos", friendly_name="Sonos", state="idle",
            ),
        ]
        s = _summarize_media(entities)
        assert s["playing_count"] == 1
        assert s["idle_count"] == 1
        assert s["now_playing"]["title"] == "Test Movie"


class TestSummarizeCovers:
    def test_mixed(self):
        entities = [
            AggregateEntity(
                entity_id="cover.r1", friendly_name="Rollo 1", state="open",
                attributes={"current_position": 100},
            ),
            AggregateEntity(
                entity_id="cover.r2", friendly_name="Rollo 2", state="closed",
                attributes={"current_position": 0},
            ),
        ]
        s = _summarize_covers(entities)
        assert s["open_count"] == 1
        assert s["closed_count"] == 1
        assert s["avg_position_pct"] == 50


class TestSummarizePower:
    def test_power_sensors(self):
        entities = [
            AggregateEntity(entity_id="sensor.p1", friendly_name="P1", state="150.5", device_class="power"),
            AggregateEntity(entity_id="sensor.p2", friendly_name="P2", state="200.0", device_class="power"),
        ]
        s = _summarize_power(entities)
        assert s["total_power_w"] == pytest.approx(350.5, abs=0.1)


class TestSummarizeMotion:
    def test_motion(self):
        entities = [
            AggregateEntity(entity_id="binary_sensor.m1", friendly_name="M1", state="on",
                            last_updated="2026-03-14T10:30:00"),
            AggregateEntity(entity_id="binary_sensor.m2", friendly_name="M2", state="off",
                            last_updated="2026-03-14T10:00:00"),
        ]
        s = _summarize_motion(entities)
        assert s["active_count"] == 1
        assert s["any_active"] is True
        assert s["last_triggered"] == "2026-03-14T10:30:00"


class TestSummarizeSecurity:
    def test_open_window(self):
        entities = [
            AggregateEntity(entity_id="binary_sensor.w1", friendly_name="Fenster Bad",
                            state="on", device_class="window"),
            AggregateEntity(entity_id="lock.front", friendly_name="Haustuer",
                            state="locked", device_class="lock"),
        ]
        s = _summarize_security(entities)
        assert s["open_count"] == 1
        assert "Fenster Bad" in s["open_contacts"]
        assert s["locked_count"] == 1
        assert s["all_secure"] is False


class TestComputeStatus:
    def test_all_unavailable(self):
        entities = [
            AggregateEntity(entity_id="sensor.t1", friendly_name="T1", state="unavailable"),
            AggregateEntity(entity_id="sensor.t2", friendly_name="T2", state="unavailable"),
        ]
        status, text = _compute_status("temperatur", entities, {})
        assert status == "unavailable"

    def test_partial_unavailable(self):
        entities = [
            AggregateEntity(entity_id="sensor.t1", friendly_name="T1", state="21"),
            AggregateEntity(entity_id="sensor.t2", friendly_name="T2", state="unavailable"),
        ]
        status, text = _compute_status("temperatur", entities, {})
        assert status == "warning"

    def test_all_ok(self):
        entities = [
            AggregateEntity(entity_id="sensor.t1", friendly_name="T1", state="21"),
        ]
        status, text = _compute_status("temperatur", entities, {"avg": 21})
        assert status == "ok"

    def test_co2_high(self):
        entities = [
            AggregateEntity(entity_id="sensor.co2", friendly_name="CO2", state="1600"),
        ]
        status, text = _compute_status("luftqualitaet", entities, {"avg": 1600})
        assert status == "critical"

    def test_battery_low(self):
        entities = [
            AggregateEntity(entity_id="sensor.b1", friendly_name="Sensor Batterie", state="15"),
        ]
        status, text = _compute_status("batterie", entities, {})
        assert status == "warning"

    def test_security_open(self):
        entities = [
            AggregateEntity(entity_id="binary_sensor.d1", friendly_name="Tuer",
                            state="on", device_class="door"),
        ]
        status, text = _compute_status("sicherheit", entities, {"open_count": 1})
        assert status == "warning"


class TestZoneAggregator:
    def test_aggregate_with_prestates(self):
        aggregator = ZoneAggregator(supervisor_token="test")
        entity_ids = ["light.test1", "light.test2", "sensor.temp1"]
        states = {
            "light.test1": {
                "entity_id": "light.test1",
                "state": "on",
                "attributes": {"friendly_name": "Licht 1", "brightness": 200},
            },
            "light.test2": {
                "entity_id": "light.test2",
                "state": "off",
                "attributes": {"friendly_name": "Licht 2"},
            },
            "sensor.temp1": {
                "entity_id": "sensor.temp1",
                "state": "21.5",
                "attributes": {"friendly_name": "Temperatur", "device_class": "temperature",
                               "unit_of_measurement": "°C"},
            },
        }
        results = aggregator.aggregate_zone(entity_ids, entity_states=states)
        cat_ids = {r.category_id for r in results}
        assert "beleuchtung" in cat_ids
        assert "temperatur" in cat_ids

    def test_aggregate_empty(self):
        aggregator = ZoneAggregator(supervisor_token="test")
        results = aggregator.aggregate_zone([], entity_states={})
        assert results == []

    def test_get_category_defs(self):
        aggregator = ZoneAggregator()
        defs = aggregator.get_category_defs()
        assert len(defs) == 11
        assert all("category_id" in d for d in defs)

    def test_invalidate_cache(self):
        aggregator = ZoneAggregator()
        aggregator._cache_ts = 999
        aggregator.invalidate_cache()
        assert aggregator._cache_ts == 0


class TestAggregateResult:
    def test_to_dict(self):
        result = AggregateResult(
            category_id="beleuchtung",
            name_de="Beleuchtung",
            icon="mdi:lightbulb-group",
            entity_count=2,
            entities=[
                AggregateEntity(entity_id="light.a", friendly_name="A", state="on"),
            ],
            summary={"on_count": 1},
            status="ok",
        )
        d = result.to_dict()
        assert d["category_id"] == "beleuchtung"
        assert d["entity_count"] == 2
        assert len(d["entities"]) == 1
        assert d["summary"]["on_count"] == 1
