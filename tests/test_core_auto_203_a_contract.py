"""CORE-AUTO-203-A proof ring: Zone/Habitus state -> Core rule decision -> notification."""
import pytest
from unittest.mock import patch

from copilot_core.autonomy.rule_engine import (
    RuleMatcher,
    RuleExecutor,
    AutomationRule,
    RuleCondition,
    RuleAction,
    ConditionOp,
    RuleStatus,
)
from copilot_core.notifications.engine import NotificationEngine


class TestZoneMoodAlertNotification:
    """CORE-AUTO-203-A: Zone/Habitus state input -> rule decision -> notification output."""

    def test_rule_matcher_zones_mood_alert_triggers_notification(self):
        """Zone mood=alert matches rule, triggers notification action."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="zone-mood-alert",
                name="Zone Mood Alert Notification",
                conditions=[
                    RuleCondition(field="zone_mood", operator=ConditionOp.EQ, value="alert")
                ],
                actions=[
                    RuleAction(
                        action_type="notify",
                        entity_id="mobile",
                        params={"message": "Zone alert in {zone_id}"},
                    )
                ],
                tags=["zone", "notification"],
            )
        )

        ctx_alert = {"zone_mood": "alert", "zone_id": "wohnzimmer"}
        matched = matcher.match_all(ctx_alert)
        assert len(matched) == 1
        assert matched[0].rule_id == "zone-mood-alert"
        assert matched[0].actions[0].action_type == "notify"

    def test_rule_matcher_normal_mood_does_not_trigger(self):
        """Zone mood=normal does not match alert rule."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="zone-mood-alert",
                name="Zone Mood Alert Notification",
                conditions=[
                    RuleCondition(field="zone_mood", operator=ConditionOp.EQ, value="alert")
                ],
                actions=[RuleAction(action_type="notify", entity_id="mobile", params={})],
                tags=["zone"],
            )
        )

        ctx_normal = {"zone_mood": "normal", "zone_id": "kueche"}
        matched = matcher.match_all(ctx_normal)
        assert len(matched) == 0

    def test_rule_matcher_person_arrive_notification(self):
        """Person arriving in zone triggers notification."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="person-arrive",
                name="Person Arrived Notification",
                conditions=[
                    RuleCondition(field="person_event", operator=ConditionOp.EQ, value="arrive"),
                    RuleCondition(field="zone_id", operator=ConditionOp.NE, value=None),
                ],
                actions=[
                    RuleAction(
                        action_type="notify",
                        entity_id="mobile",
                        params={"message": "{person_id} arrived in {zone_id}"},
                    )
                ],
                tags=["presence", "notification"],
            )
        )

        ctx_arrive = {"person_event": "arrive", "person_id": "andreas", "zone_id": "wohnzimmer"}
        matched = matcher.match_all(ctx_arrive)
        assert len(matched) == 1
        assert matched[0].rule_id == "person-arrive"

    def test_rule_executor_zone_alert_executes_notification_with_interpolated_message(self):
        """Matched zone alert rule executes the existing notification delivery seam."""
        rule = AutomationRule(
            rule_id="zone-mood-alert",
            name="Zone Mood Alert Notification",
            conditions=[
                RuleCondition(field="zone_mood", operator=ConditionOp.EQ, value="alert")
            ],
            actions=[
                RuleAction(
                    action_type="notify",
                    entity_id="mobile",
                    params={"message": "Zone alert in {zone_id}"},
                )
            ],
            tags=["zone", "notification"],
        )
        executor = RuleExecutor()
        ctx_alert = {"zone_mood": "alert", "zone_id": "wohnzimmer"}

        with patch("copilot_core.proactive_engine.ProactiveContextEngine") as proactive_cls:
            proactive = proactive_cls.return_value
            proactive.deliver_suggestion.return_value = {"ok": True, "method": "notification"}

            result = executor.execute(rule, ctx_alert)

        proactive.deliver_suggestion.assert_called_once_with(
            {"type": "automation", "message": "Zone alert in wohnzimmer"},
            method="notification",
        )
        assert result["action_results"][0]["ok"] is True
        assert result["action_results"][0]["result"]["notified"] is True
        assert result["action_results"][0]["result"]["message"] == "Zone alert in wohnzimmer"
        assert rule.trigger_count == 1
        assert executor.get_execution_log(limit=1)[0]["rule_id"] == "zone-mood-alert"

    def test_notification_engine_notify_returns_notification_object(self):
        """NotificationEngine.notify() returns a Notification object."""
        engine = NotificationEngine()
        result = engine.notify(
            source="test",
            title="Zone Alert",
            message="Wohnzimmer mood changed to alert",
        )
        assert result is not None
        assert hasattr(result, 'id')
        assert result.title == "Zone Alert"
        assert result.delivered == False  # not yet delivered, just queued

    def test_notification_engine_stats_returns_counts(self):
        """NotificationEngine.get_stats() returns truthy stats."""
        engine = NotificationEngine()
        stats = engine.get_stats()
        assert isinstance(stats, dict)
        assert "total_notifications" in stats or "pending_count" in stats

    def test_notification_engine_history_returns_list(self):
        """NotificationEngine.get_history() returns a list."""
        engine = NotificationEngine()
        history = engine.get_history()
        assert isinstance(history, list)

    def test_rule_matcher_list_rules_with_tag_filter(self):
        """RuleMatcher.list_rules(tag=...) filters correctly."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="zone-alert",
                name="Zone Alert",
                conditions=[],
                actions=[],
                tags=["zone", "notification"],
            )
        )
        matcher.add_rule(
            AutomationRule(
                rule_id="energy-save",
                name="Energy Saver",
                conditions=[],
                actions=[],
                tags=["energy"],
            )
        )

        zone_rules = matcher.list_rules(tag="zone")
        assert len(zone_rules) == 1
        assert zone_rules[0].rule_id == "zone-alert"

        all_rules = matcher.list_rules()
        assert len(all_rules) == 2

    def test_rule_matcher_list_rules_with_status_filter(self):
        """RuleMatcher.list_rules(status=...) filters correctly."""
        matcher = RuleMatcher()
        matcher.add_rule(
            AutomationRule(
                rule_id="active-rule",
                name="Active Rule",
                conditions=[],
                actions=[],
                status=RuleStatus.ACTIVE,
            )
        )
        matcher.add_rule(
            AutomationRule(
                rule_id="paused-rule",
                name="Paused Rule",
                conditions=[],
                actions=[],
                status=RuleStatus.PAUSED,
            )
        )

        active = matcher.list_rules(status=RuleStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].rule_id == "active-rule"

        paused = matcher.list_rules(status=RuleStatus.PAUSED)
        assert len(paused) == 1
        assert paused[0].rule_id == "paused-rule"
