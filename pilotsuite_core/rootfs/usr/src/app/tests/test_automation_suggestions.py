"""Tests for Automation Suggestion Engine (v5.9.0)."""

import pytest
from copilot_core.automations.suggestion_engine import (
    AutomationSuggestion,
    AutomationSuggestionEngine,
)


@pytest.fixture
def engine():
    return AutomationSuggestionEngine()


# ═══════════════════════════════════════════════════════════════════════════
# Schedule-based Suggestions
# ═══════════════════════════════════════════════════════════════════════════


class TestScheduleSuggestions:
    def test_generates_suggestion(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        assert isinstance(s, AutomationSuggestion)
        assert s.category == "time"

    def test_has_automation_yaml(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        auto = s.automation_yaml
        assert "alias" in auto
        assert "trigger" in auto
        assert "action" in auto

    def test_trigger_is_time(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        trigger = s.automation_yaml["trigger"][0]
        assert trigger["platform"] == "time"
        assert trigger["at"] == "10:00:00"

    def test_weekday_condition(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12, days="weekday")
        condition = s.automation_yaml["condition"][0]
        assert "mon" in condition["weekday"]
        assert "sat" not in condition["weekday"]

    def test_daily_condition(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12, days="daily")
        condition = s.automation_yaml["condition"][0]
        assert "sat" in condition["weekday"]
        assert "sun" in condition["weekday"]

    def test_action_turns_on_and_off(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        actions = s.automation_yaml["action"]
        assert actions[0]["service"] == "switch.turn_on"
        assert actions[2]["service"] == "switch.turn_off"

    def test_delay_matches_duration(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 14)
        delay = s.automation_yaml["action"][1]["delay"]
        assert delay["hours"] == 4

    def test_known_device_entity(self, engine):
        s = engine.suggest_from_schedule("ev_charger", 0, 4)
        entity = s.automation_yaml["action"][0]["target"]["entity_id"]
        assert entity == "switch.ev_charger"

    def test_unknown_device_fallback(self, engine):
        s = engine.suggest_from_schedule("pool_pump", 14, 16)
        entity = s.automation_yaml["action"][0]["target"]["entity_id"]
        assert entity == "switch.pool_pump"

    def test_confidence_positive(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        assert s.confidence > 0

    def test_stored_in_engine(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        items = engine.get_suggestions()
        assert len(items) == 1
        assert items[0]["id"] == s.id


# ═══════════════════════════════════════════════════════════════════════════
# Solar-based Suggestions
# ═══════════════════════════════════════════════════════════════════════════


class TestSolarSuggestions:
    def test_generates_suggestion(self, engine):
        s = engine.suggest_from_solar("ev_charger", 5.0)
        assert s.category == "energy"

    def test_trigger_is_numeric_state(self, engine):
        s = engine.suggest_from_solar("dishwasher", 3.0)
        trigger = s.automation_yaml["trigger"][0]
        assert trigger["platform"] == "numeric_state"
        assert trigger["above"] == 3.0

    def test_condition_checks_off(self, engine):
        s = engine.suggest_from_solar("washer")
        condition = s.automation_yaml["condition"][0]
        assert condition["state"] == "off"

    def test_savings_positive(self, engine):
        s = engine.suggest_from_solar("ev_charger")
        assert s.estimated_savings_eur > 0


# ═══════════════════════════════════════════════════════════════════════════
# Comfort-based Suggestions
# ═══════════════════════════════════════════════════════════════════════════


class TestComfortSuggestions:
    def test_co2_suggestion(self, engine):
        s = engine.suggest_from_comfort("co2", 1000, "switch.ventilation")
        assert s.category == "comfort"
        trigger = s.automation_yaml["trigger"][0]
        assert trigger["above"] == 1000

    def test_temperature_low_uses_below(self, engine):
        s = engine.suggest_from_comfort("temperature_low", 18, "switch.heater")
        trigger = s.automation_yaml["trigger"][0]
        assert trigger["below"] == 18

    def test_custom_service(self, engine):
        s = engine.suggest_from_comfort("humidity_high", 70, "switch.dehumidifier", "switch.turn_on")
        action = s.automation_yaml["action"][0]
        assert action["service"] == "switch.turn_on"

    def test_unknown_factor(self, engine):
        s = engine.suggest_from_comfort("noise", 80, "switch.noise_cancel")
        assert s.automation_yaml["trigger"][0]["above"] == 80


# ═══════════════════════════════════════════════════════════════════════════
# Presence-based Suggestions
# ═══════════════════════════════════════════════════════════════════════════


class TestPresenceSuggestions:
    def test_generates_suggestion(self, engine):
        s = engine.suggest_from_presence(away_minutes=30)
        assert s.category == "presence"

    def test_trigger_is_state(self, engine):
        s = engine.suggest_from_presence()
        trigger = s.automation_yaml["trigger"][0]
        assert trigger["platform"] == "state"
        assert trigger["to"] == "not_home"

    def test_custom_away_minutes(self, engine):
        s = engine.suggest_from_presence(away_minutes=60)
        trigger = s.automation_yaml["trigger"][0]
        assert trigger["for"]["minutes"] == 60

    def test_custom_entities(self, engine):
        entities = ["light.office", "light.garage"]
        s = engine.suggest_from_presence(entities=entities)
        target = s.automation_yaml["action"][0]["target"]["entity_id"]
        assert target == entities

    def test_high_confidence(self, engine):
        s = engine.suggest_from_presence()
        assert s.confidence >= 0.8


# ═══════════════════════════════════════════════════════════════════════════
# Get / Accept / Dismiss
# ═══════════════════════════════════════════════════════════════════════════


class TestManagement:
    def test_get_all_suggestions(self, engine):
        engine.suggest_from_schedule("washer", 10, 12)
        engine.suggest_from_solar("ev_charger")
        engine.suggest_from_presence()
        items = engine.get_suggestions()
        assert len(items) == 3

    def test_filter_by_category(self, engine):
        engine.suggest_from_schedule("washer", 10, 12)
        engine.suggest_from_solar("ev_charger")
        items = engine.get_suggestions(category="energy")
        assert len(items) == 1
        assert items[0]["category"] == "energy"

    def test_accept_suggestion(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        result = engine.accept_suggestion(s.id)
        assert result["accepted"] is True

    def test_dismiss_suggestion(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        engine.dismiss_suggestion(s.id)
        items = engine.get_suggestions()
        assert len(items) == 0  # Dismissed hidden by default

    def test_include_dismissed(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        engine.dismiss_suggestion(s.id)
        items = engine.get_suggestions(include_dismissed=True)
        assert len(items) == 1

    def test_accept_nonexistent(self, engine):
        result = engine.accept_suggestion("nonexistent")
        assert result is None

    def test_get_yaml(self, engine):
        s = engine.suggest_from_schedule("washer", 10, 12)
        yaml_data = engine.get_suggestion_yaml(s.id)
        assert "alias" in yaml_data
        assert "trigger" in yaml_data

    def test_get_yaml_nonexistent(self, engine):
        result = engine.get_suggestion_yaml("nope")
        assert result is None

    def test_sorted_by_confidence(self, engine):
        engine.suggest_from_comfort("co2", 1000, "switch.vent")  # 0.7
        engine.suggest_from_presence()  # 0.85
        engine.suggest_from_schedule("washer", 10, 12)  # 0.8
        items = engine.get_suggestions()
        confidences = [i["confidence"] for i in items]
        assert confidences == sorted(confidences, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════════


class TestSuggestionPersistence:
    def test_state_survives_restart(self, tmp_path):
        state_path = tmp_path / "suggestion_engine_state.json"
        engine = AutomationSuggestionEngine(persist_state=True, storage_path=state_path)

        s = engine.suggest_from_schedule("washer", 6, 8)
        proposal = engine.accept_suggestion(s.id)
        assert proposal is not None
        proposal_id = proposal["proposal_id"]

        intent = engine.execute_proposal(proposal_id, dry_run=True)
        assert intent is not None

        assert state_path.exists()

        restarted = AutomationSuggestionEngine(persist_state=True, storage_path=state_path)
        restored_suggestions = restarted.get_suggestions(include_accepted=True)
        restored_proposals = restarted.get_proposals(include_executed=True)
        restored_intent = restarted.get_action_intent(intent["intent_id"])

        assert len(restored_suggestions) == 1
        assert restored_suggestions[0]["id"] == s.id
        assert restored_suggestions[0]["accepted"] is True
        assert len(restored_proposals) == 1
        assert restored_proposals[0]["proposal_id"] == proposal_id
        assert restored_proposals[0]["action_intent_id"] == intent["intent_id"]
        assert restored_intent is not None
        assert restored_intent["status"] == "ready"

        # ensure counters continue after restore
        another = restarted.suggest_from_solar("ev_charger")
        assert another.id != s.id
        assert another.id.startswith("auto-")

    def test_proposal_intent_link_restored(self, tmp_path):
        state_path = tmp_path / "proposal_state.json"
        engine = AutomationSuggestionEngine(persist_state=True, storage_path=state_path)

        s = engine.suggest_from_comfort("co2", 1000, "switch.ventilation")
        proposal = engine.propose_suggestion(s.id)
        assert proposal is not None
        proposal_id = proposal["proposal_id"]
        intent = engine.create_action_intent(proposal_id)
        assert intent is not None

        restarted = AutomationSuggestionEngine(persist_state=True, storage_path=state_path)
        persisted = restarted.get_proposal(proposal_id)
        assert persisted is not None
        assert persisted["action_intent_id"] == intent["intent_id"]

        persisted_intent = restarted.get_action_intent(persisted["action_intent_id"])
        assert persisted_intent is not None
        assert persisted_intent["params"]["suggestion_id"] == s.id
