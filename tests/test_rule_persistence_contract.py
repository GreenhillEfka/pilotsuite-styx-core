"""CORE-HARDEN-204 proof ring: RuleMatcher save/load persistence."""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from copilot_core.autonomy.rule_engine import (
    RuleMatcher,
    AutomationRule,
    RuleCondition,
    RuleAction,
    ConditionOp,
    RuleStatus,
)


class TestRulePersistenceContract:
    """CORE-HARDEN-204: RuleMatcher must persist custom rules across app restarts."""

    def test_rule_matcher_save_serializes_rules_to_json_file(self):
        """RuleMatcher.save() writes all rules as JSON to the given file path."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="zone-alert-1",
                name="Zone Alert",
                conditions=[RuleCondition(field="zone_mood", operator=ConditionOp.EQ, value="alert")],
                actions=[RuleAction(action_type="notify", entity_id="mobile", params={})],
                tags=["zone", "notification"],
            )
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            result = matcher.save(tmp_path)
            assert result is True
            assert os.path.exists(tmp_path)
            with open(tmp_path) as fh:
                data = json.load(fh)
            assert "rules" in data
            assert len(data["rules"]) == 1
            assert data["rules"][0]["rule_id"] == "zone-alert-1"
        finally:
            os.unlink(tmp_path)

    def test_rule_matcher_load_restores_rules_from_json_file(self):
        """RuleMatcher.load() restores rules from a JSON file."""
        matcher = RuleMatcher()

        payload = {
            "rules": [
                {
                    "rule_id": "energy-surplus",
                    "name": "Energy Surplus Alert",
                    "description": "Notify when solar surplus > 2kW",
                    "conditions": [{"field": "pv_power_kw", "operator": "gt", "value": 2.0}],
                    "actions": [{"action_type": "notify", "entity_id": "mobile", "params": {}}],
                    "status": "active",
                    "tags": ["energy"],
                    "priority": 50,
                }
            ]
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(payload, f)
            tmp_path = f.name

        try:
            result = matcher.load(tmp_path)
            assert result is True
            restored = matcher.get_rule("energy-surplus")
            assert restored is not None
            assert restored.rule_id == "energy-surplus"
            assert restored.name == "Energy Surplus Alert"
            assert restored.conditions[0].field == "pv_power_kw"
            assert restored.conditions[0].operator == ConditionOp.GT
        finally:
            os.unlink(tmp_path)

    def test_custom_rule_survives_restart_via_save_load_roundtrip(self):
        """Custom rules survive a restart when saved and loaded."""
        matcher1 = RuleMatcher()
        matcher1.add_rule(
            AutomationRule(
                rule_id="person-arrive-notify",
                name="Person Arrived Notification",
                conditions=[
                    RuleCondition(field="person_event", operator=ConditionOp.EQ, value="arrive"),
                    RuleCondition(field="zone_id", operator=ConditionOp.NE, value=None),
                ],
                actions=[RuleAction(action_type="notify", entity_id="mobile", params={})],
                tags=["presence", "notification"],
            )
        )
        matcher1.add_rule(
            AutomationRule(
                rule_id="zone-mood-alert",
                name="Zone Mood Alert",
                conditions=[RuleCondition(field="zone_mood", operator=ConditionOp.EQ, value="alert")],
                actions=[RuleAction(action_type="notify", entity_id="mobile", params={})],
                tags=["zone", "alert"],
            )
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            matcher1.save(tmp_path)

            # Simulate app restart — fresh RuleMatcher instance
            matcher2 = RuleMatcher()
            assert matcher2.get_rule("person-arrive-notify") is None  # not loaded yet

            matcher2.load(tmp_path)

            rule1 = matcher2.get_rule("person-arrive-notify")
            assert rule1 is not None
            assert rule1.name == "Person Arrived Notification"
            assert len(rule1.conditions) == 2
            assert rule1.tags == ["presence", "notification"]

            rule2 = matcher2.get_rule("zone-mood-alert")
            assert rule2 is not None
            assert rule2.rule_id == "zone-mood-alert"

        finally:
            os.unlink(tmp_path)

    def test_save_load_roundtrip_with_multiple_rules(self):
        """Multiple rules survive save/load roundtrip correctly."""
        matcher = RuleMatcher()
        for i in range(5):
            matcher.add_rule(
                AutomationRule(
                    rule_id=f"rule-{i}",
                    name=f"Rule {i}",
                    conditions=[RuleCondition(field="x", operator=ConditionOp.GT, value=i)],
                    actions=[RuleAction(action_type="notify", entity_id="mobile", params={})],
                    tags=[f"tag-{i}"],
                )
            )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            matcher.save(tmp_path)

            matcher2 = RuleMatcher()
            matcher2.load(tmp_path)

            assert len(matcher2.list_rules()) == 5
            for i in range(5):
                r = matcher2.get_rule(f"rule-{i}")
                assert r is not None
                assert r.name == f"Rule {i}"

        finally:
            os.unlink(tmp_path)

    def test_save_returns_false_for_missing_directory(self):
        """RuleMatcher.save() returns False when parent directory does not exist."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="test-rule",
                name="Test",
                conditions=[],
                actions=[],
            )
        )
        result = matcher.save("/nonexistent/path/that/does/not/exist/rules.json")
        assert result is False

    def test_load_returns_false_for_missing_file(self):
        """RuleMatcher.load() returns False when file does not exist."""
        matcher = RuleMatcher()
        result = matcher.load("/nonexistent/path/rules.json")
        assert result is False

    def test_load_clears_existing_rules_before_restore(self):
        """load() replaces existing in-memory rules with loaded ones."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="old-rule",
                name="Old Rule",
                conditions=[],
                actions=[],
            )
        )
        assert matcher.get_rule("old-rule") is not None

        payload = {
            "rules": [
                {
                    "rule_id": "new-rule",
                    "name": "New Rule",
                    "description": "",
                    "conditions": [],
                    "actions": [],
                    "status": "active",
                    "tags": [],
                    "priority": 0,
                }
            ]
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(payload, f)
            tmp_path = f.name

        try:
            matcher.load(tmp_path)
            assert matcher.get_rule("old-rule") is None  # cleared
            assert matcher.get_rule("new-rule") is not None  # loaded
        finally:
            os.unlink(tmp_path)