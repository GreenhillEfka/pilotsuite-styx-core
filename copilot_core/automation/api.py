"""Automation Analytics API — Slice 54."""

from flask import Blueprint, jsonify, request
from typing import List, Optional

from .analytics_store import get_automation_analytics_store


def create_automation_analytics_blueprint() -> Blueprint:
    """Automation Analytics Blueprint erstellen."""
    bp = Blueprint("automation_analytics", __name__, url_prefix="/api/v1/automation/analytics")

    @bp.route("/executions", methods=["GET"])
    def get_execution_history():
        """Automation-Execution-Historie abrufen."""
        store = get_automation_analytics_store()

        time_range_start = request.args.get("time_range_start")
        time_range_end = request.args.get("time_range_end")
        automation_id = request.args.get("automation_id")
        status = request.args.get("status")
        trigger_type = request.args.get("trigger_type")
        zone_id = request.args.get("zone_id")
        limit = int(request.args.get("limit", 100))

        history = store.build_execution_history(
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            automation_id=automation_id,
            status=status,
            trigger_type=trigger_type,
            zone_id=zone_id,
            limit=limit,
        )

        return jsonify({
            "executions": {
                "entries": [
                    {
                        "entry_id": e.entry_id,
                        "automation_id": e.automation_id,
                        "automation_name": e.automation_name,
                        "trigger_type": e.trigger_type,
                        "status": e.status,
                        "zone_id": e.zone_id,
                        "zone_name": e.zone_name,
                        "module_id": e.module_id,
                        "module_name": e.module_name,
                        "triggered_at": e.triggered_at,
                        "started_at": e.started_at,
                        "completed_at": e.completed_at,
                        "duration_seconds": e.duration_seconds,
                        "error_message": e.error_message,
                        "actions_executed": e.actions_executed,
                        "actions_failed": e.actions_failed,
                        "entities_affected": e.entities_affected,
                    }
                    for e in history.entries
                ],
                "total_executions": history.total_executions,
                "total_completed": history.total_completed,
                "total_failed": history.total_failed,
                "total_skipped": history.total_skipped,
                "total_blocked": history.total_blocked,
                "avg_duration_seconds": history.avg_duration_seconds,
                "revision": history.revision,
                "latest_change_at": history.latest_change_at,
                "time_range_start": history.time_range_start,
                "time_range_end": history.time_range_end,
            }
        })

    @bp.route("/rules", methods=["GET"])
    def get_rule_patterns():
        """Rule-spezifische Automation-Patterns abrufen."""
        store = get_automation_analytics_store()

        automation_ids_param = request.args.get("automation_ids")
        automation_ids: Optional[List[str]] = None
        if automation_ids_param:
            automation_ids = automation_ids_param.split(",")

        patterns = store.build_rule_patterns(automation_ids=automation_ids)

        return jsonify({
            "rules": {
                "patterns": [
                    {
                        "automation_id": p.automation_id,
                        "automation_name": p.automation_name,
                        "trigger_type": p.trigger_type,
                        "total_executions": p.total_executions,
                        "completed_count": p.completed_count,
                        "failed_count": p.failed_count,
                        "skipped_count": p.skipped_count,
                        "success_rate": p.success_rate,
                        "avg_duration_seconds": p.avg_duration_seconds,
                        "avg_actions_executed": p.avg_actions_executed,
                        "avg_entities_affected": p.avg_entities_affected,
                        "failure_rate": p.failure_rate,
                        "last_execution_at": p.last_execution_at,
                        "executions_last_24_hours": p.executions_last_24_hours,
                        "executions_last_7_days": p.executions_last_7_days,
                        "most_common_trigger": p.most_common_trigger,
                        "peak_execution_hour": p.peak_execution_hour,
                        "zones_affected": p.zones_affected,
                    }
                    for p in patterns.patterns
                ],
                "total_automations": patterns.total_automations,
                "automations_with_executions": patterns.automations_with_executions,
                "revision": patterns.revision,
                "latest_change_at": patterns.latest_change_at,
            }
        })

    @bp.route("/effectiveness", methods=["GET"])
    def get_effectiveness():
        """Automation-Effectiveness-Metriken abrufen."""
        store = get_automation_analytics_store()
        effectiveness = store.get_effectiveness_metrics()

        return jsonify({
            "effectiveness": {
                "total_executions_analyzed": effectiveness.total_executions_analyzed,
                "executions_by_status": effectiveness.executions_by_status,
                "executions_by_trigger": effectiveness.executions_by_trigger,
                "overall_success_rate": effectiveness.overall_success_rate,
                "overall_failure_rate": effectiveness.overall_failure_rate,
                "avg_duration_by_trigger": effectiveness.avg_duration_by_trigger,
                "failure_rate_by_trigger": effectiveness.failure_rate_by_trigger,
                "automations_with_regular_executions": effectiveness.automations_with_regular_executions,
                "automations_with_rare_executions": effectiveness.automations_with_rare_executions,
                "peak_automation_time": effectiveness.peak_automation_time,
                "reliability_score": effectiveness.reliability_score,
                "revision": effectiveness.revision,
                "latest_change_at": effectiveness.latest_change_at,
            }
        })

    @bp.route("/summary", methods=["GET"])
    def get_summary():
        """Zusammenfassung aller Automation-Analytics abrufen."""
        store = get_automation_analytics_store()
        summary = store.build_summary()

        return jsonify({
            "summary": {
                "executions": {
                    "total_executions": summary.usage.total_executions,
                    "total_completed": summary.usage.total_completed,
                    "total_failed": summary.usage.total_failed,
                    "total_skipped": summary.usage.total_skipped,
                    "total_blocked": summary.usage.total_blocked,
                    "avg_duration_seconds": summary.usage.avg_duration_seconds,
                    "revision": summary.usage.revision,
                    "latest_change_at": summary.usage.latest_change_at,
                },
                "rules": {
                    "total_automations": summary.patterns.total_automations,
                    "automations_with_executions": summary.patterns.automations_with_executions,
                    "revision": summary.patterns.revision,
                    "latest_change_at": summary.patterns.latest_change_at,
                },
                "effectiveness": {
                    "total_executions_analyzed": summary.effectiveness.total_executions_analyzed,
                    "overall_success_rate": summary.effectiveness.overall_success_rate,
                    "reliability_score": summary.effectiveness.reliability_score,
                    "revision": summary.effectiveness.revision,
                    "latest_change_at": summary.effectiveness.latest_change_at,
                },
                "summary_revision": summary.summary_revision,
                "latest_change_at": summary.latest_change_at,
            }
        })

    return bp
