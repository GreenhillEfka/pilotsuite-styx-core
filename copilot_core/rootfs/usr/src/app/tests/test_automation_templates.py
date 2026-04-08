"""Tests for Automation Templates engine (v6.9.0)."""

import pytest
from copilot_core.hub.automation_templates import (
    AutomationTemplateEngine,
    AutomationTemplate,
    TemplateVariable,
    GeneratedAutomation,
    TemplateSummary,
)


@pytest.fixture
def engine():
    return AutomationTemplateEngine()


# ── Built-in templates ────────────────────────────────────────────────────


class TestBuiltinTemplates:
    def test_builtin_template_count(self, engine):
        templates = engine.get_templates()
        assert len(templates) == 9

    def test_builtin_template_ids(self, engine):
        templates = engine.get_templates()
        ids = {t["template_id"] for t in templates}
        assert "light_motion" in ids
        assert "night_lights" in ids
        assert "heating_schedule" in ids
        assert "window_heating" in ids
        assert "door_alert" in ids
        assert "energy_peak_alert" in ids
        assert "welcome_home" in ids
        assert "goodnight" in ids
        assert "appliance_done" in ids

    def test_template_details(self, engine):
        detail = engine.get_template_detail("light_motion")
        assert detail is not None
        assert detail["name_de"] == "Licht bei Bewegung"
        assert detail["category"] == "lighting"
        assert detail["difficulty"] == "easy"
        assert len(detail["variables"]) == 3

    def test_template_not_found(self, engine):
        assert engine.get_template_detail("nonexistent") is None


# ── Filter and search ─────────────────────────────────────────────────────


class TestFilters:
    def test_filter_by_category(self, engine):
        templates = engine.get_templates(category="lighting")
        assert len(templates) >= 2
        assert all(t["category"] == "lighting" for t in templates)

    def test_filter_by_difficulty(self, engine):
        templates = engine.get_templates(difficulty="easy")
        assert len(templates) >= 3
        assert all(t["difficulty"] == "easy" for t in templates)

    def test_search_by_name(self, engine):
        templates = engine.get_templates(search="Bewegung")
        assert len(templates) >= 1
        assert templates[0]["template_id"] == "light_motion"

    def test_search_by_tag(self, engine):
        templates = engine.get_templates(search="security")
        assert len(templates) >= 1

    def test_search_no_results(self, engine):
        templates = engine.get_templates(search="nonexistent_xyz")
        assert len(templates) == 0


# ── Categories ─────────────────────────────────────────────────────────────


class TestCategories:
    def test_get_categories(self, engine):
        categories = engine.get_categories()
        assert len(categories) >= 4
        names = {c["category"] for c in categories}
        assert "lighting" in names
        assert "climate" in names
        assert "security" in names

    def test_category_counts(self, engine):
        categories = engine.get_categories()
        total = sum(c["count"] for c in categories)
        assert total == 9


# ── Generation ─────────────────────────────────────────────────────────────


class TestGeneration:
    def test_generate_automation(self, engine):
        gen = engine.generate_automation("light_motion", {
            "motion_sensor": "binary_sensor.flur_motion",
            "light_entity": "light.flur",
            "timeout_min": "3",
        })
        assert gen is not None
        assert gen.template_id == "light_motion"
        assert gen.variables["motion_sensor"] == "binary_sensor.flur_motion"

    def test_generate_with_name(self, engine):
        gen = engine.generate_automation("light_motion", {
            "motion_sensor": "binary_sensor.flur_motion",
            "light_entity": "light.flur",
        }, name="Flur Licht Automatik")
        assert gen.name == "Flur Licht Automatik"

    def test_generate_yaml_preview(self, engine):
        gen = engine.generate_automation("light_motion", {
            "motion_sensor": "binary_sensor.flur_motion",
            "light_entity": "light.flur",
            "timeout_min": "3",
        })
        assert "binary_sensor.flur_motion" in gen.yaml_preview
        assert "alias:" in gen.yaml_preview

    def test_generate_invalid_template(self, engine):
        gen = engine.generate_automation("nonexistent", {})
        assert gen is None

    def test_generate_missing_required_variable(self, engine):
        gen = engine.generate_automation("light_motion", {
            "light_entity": "light.flur",
            # missing motion_sensor which is required and has no default
        })
        assert gen is None

    def test_generate_with_defaults(self, engine):
        gen = engine.generate_automation("light_motion", {
            "motion_sensor": "binary_sensor.flur_motion",
            "light_entity": "light.flur",
            # timeout_min has default "5" so should auto-fill
        })
        assert gen is not None
        assert gen.variables["timeout_min"] == "5"

    def test_generation_increments_usage(self, engine):
        engine.generate_automation("light_motion", {
            "motion_sensor": "binary_sensor.flur_motion",
            "light_entity": "light.flur",
        })
        detail = engine.get_template_detail("light_motion")
        assert detail["usage_count"] == 1


# ── Rating ─────────────────────────────────────────────────────────────────


class TestRating:
    def test_rate_template(self, engine):
        result = engine.rate_template("light_motion", 4.5)
        assert result is True
        detail = engine.get_template_detail("light_motion")
        assert detail["rating"] == 4.5

    def test_rate_running_average(self, engine):
        engine.rate_template("light_motion", 4.0)
        engine.rate_template("light_motion", 5.0)
        detail = engine.get_template_detail("light_motion")
        assert detail["rating"] == 4.5

    def test_rate_invalid_template(self, engine):
        result = engine.rate_template("nonexistent", 4.0)
        assert result is False

    def test_rate_out_of_range(self, engine):
        result = engine.rate_template("light_motion", 6.0)
        assert result is False


# ── Custom templates ──────────────────────────────────────────────────────


class TestCustomTemplates:
    def test_register_custom(self, engine):
        result = engine.register_template(
            "custom_alarm", "Benutzerdefinierter Alarm",
            "Eigene Alarm-Automatisierung", category="security",
        )
        assert result is True
        templates = engine.get_templates()
        assert len(templates) == 10

    def test_duplicate_rejected(self, engine):
        result = engine.register_template("light_motion", "Dup", "Dup")
        assert result is False

    def test_custom_with_variables(self, engine):
        result = engine.register_template(
            "custom_sensor", "Sensor-Check",
            "Prüft Sensorwerte", category="energy",
            variables=[
                {"name": "sensor", "description_de": "Sensor", "var_type": "entity"},
            ],
        )
        assert result is True
        detail = engine.get_template_detail("custom_sensor")
        assert len(detail["variables"]) == 1


# ── Summary ────────────────────────────────────────────────────────────────


class TestSummary:
    def test_summary_counts(self, engine):
        summary = engine.get_summary()
        assert summary.total_templates == 9
        assert summary.generated_count == 0

    def test_summary_after_generation(self, engine):
        engine.generate_automation("light_motion", {
            "motion_sensor": "binary_sensor.m",
            "light_entity": "light.l",
        })
        summary = engine.get_summary()
        assert summary.generated_count == 1

    def test_summary_categories(self, engine):
        summary = engine.get_summary()
        assert len(summary.categories) >= 4
        assert "lighting" in summary.categories

    def test_summary_popular(self, engine):
        engine.generate_automation("light_motion", {
            "motion_sensor": "binary_sensor.m",
            "light_entity": "light.l",
        })
        summary = engine.get_summary()
        assert len(summary.popular) >= 1
        assert summary.popular[0]["template_id"] == "light_motion"
