"""Scheduler Analytics API — Slice 53."""

from flask import Blueprint, jsonify, request
from typing import List, Optional

from .analytics_store import get_scheduler_analytics_store


def create_scheduler_analytics_blueprint() -> Blueprint:
    """Scheduler Analytics Blueprint erstellen."""
    bp = Blueprint("scheduler_analytics", __name__, url_prefix="/api/v1/scheduler/analytics")

    @bp.route("/executions", methods=["GET"])
    def get_execution_history():
        """Scheduler-Job-Execution-Historie abrufen."""
        store = get_scheduler_analytics_store()

        time_range_start = request.args.get("time_range_start")
        time_range_end = request.args.get("time_range_end")
        job_id = request.args.get("job_id")
        status = request.args.get("status")
        job_type = request.args.get("job_type")
        limit = int(request.args.get("limit", 100))

        history = store.build_execution_history(
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            job_id=job_id,
            status=status,
            job_type=job_type,
            limit=limit,
        )

        return jsonify({
            "executions": {
                "entries": [
                    {
                        "entry_id": e.entry_id,
                        "job_id": e.job_id,
                        "job_name": e.job_name,
                        "job_type": e.job_type,
                        "status": e.status,
                        "scheduled_at": e.scheduled_at,
                        "started_at": e.started_at,
                        "completed_at": e.completed_at,
                        "duration_seconds": e.duration_seconds,
                        "error_message": e.error_message,
                        "retry_count": e.retry_count,
                        "triggered_by": e.triggered_by,
                        "zone_id": e.zone_id,
                        "zone_name": e.zone_name,
                    }
                    for e in history.entries
                ],
                "total_executions": history.total_executions,
                "total_completed": history.total_completed,
                "total_failed": history.total_failed,
                "total_skipped": history.total_skipped,
                "total_cancelled": history.total_cancelled,
                "avg_duration_seconds": history.avg_duration_seconds,
                "revision": history.revision,
                "latest_change_at": history.latest_change_at,
                "time_range_start": history.time_range_start,
                "time_range_end": history.time_range_end,
            }
        })

    @bp.route("/jobs", methods=["GET"])
    def get_job_patterns():
        """Job-spezifische Scheduler-Patterns abrufen."""
        store = get_scheduler_analytics_store()

        job_ids_param = request.args.get("job_ids")
        job_ids: Optional[List[str]] = None
        if job_ids_param:
            job_ids = job_ids_param.split(",")

        patterns = store.build_job_patterns(job_ids=job_ids)

        return jsonify({
            "jobs": {
                "patterns": [
                    {
                        "job_id": p.job_id,
                        "job_name": p.job_name,
                        "job_type": p.job_type,
                        "total_executions": p.total_executions,
                        "completed_count": p.completed_count,
                        "failed_count": p.failed_count,
                        "skipped_count": p.skipped_count,
                        "success_rate": p.success_rate,
                        "avg_duration_seconds": p.avg_duration_seconds,
                        "min_duration_seconds": p.min_duration_seconds,
                        "max_duration_seconds": p.max_duration_seconds,
                        "failure_rate": p.failure_rate,
                        "last_execution_at": p.last_execution_at,
                        "next_scheduled_at": p.next_scheduled_at,
                        "executions_last_24_hours": p.executions_last_24_hours,
                        "executions_last_7_days": p.executions_last_7_days,
                        "most_common_status": p.most_common_status,
                        "peak_execution_hour": p.peak_execution_hour,
                    }
                    for p in patterns.patterns
                ],
                "total_jobs": patterns.total_jobs,
                "jobs_with_executions": patterns.jobs_with_executions,
                "revision": patterns.revision,
                "latest_change_at": patterns.latest_change_at,
            }
        })

    @bp.route("/effectiveness", methods=["GET"])
    def get_effectiveness():
        """Scheduler-Effectiveness-Metriken abrufen."""
        store = get_scheduler_analytics_store()
        effectiveness = store.get_effectiveness_metrics()

        return jsonify({
            "effectiveness": {
                "total_executions_analyzed": effectiveness.total_executions_analyzed,
                "executions_by_status": effectiveness.executions_by_status,
                "executions_by_type": effectiveness.executions_by_type,
                "overall_success_rate": effectiveness.overall_success_rate,
                "overall_failure_rate": effectiveness.overall_failure_rate,
                "avg_duration_by_job_type": effectiveness.avg_duration_by_job_type,
                "failure_rate_by_job_type": effectiveness.failure_rate_by_job_type,
                "jobs_with_regular_executions": effectiveness.jobs_with_regular_executions,
                "jobs_with_rare_executions": effectiveness.jobs_with_rare_executions,
                "peak_execution_time": effectiveness.peak_execution_time,
                "reliability_score": effectiveness.reliability_score,
                "revision": effectiveness.revision,
                "latest_change_at": effectiveness.latest_change_at,
            }
        })

    @bp.route("/summary", methods=["GET"])
    def get_summary():
        """Zusammenfassung aller Scheduler-Analytics abrufen."""
        store = get_scheduler_analytics_store()
        summary = store.build_summary()

        return jsonify({
            "summary": {
                "executions": {
                    "total_executions": summary.usage.total_executions,
                    "total_completed": summary.usage.total_completed,
                    "total_failed": summary.usage.total_failed,
                    "total_skipped": summary.usage.total_skipped,
                    "total_cancelled": summary.usage.total_cancelled,
                    "avg_duration_seconds": summary.usage.avg_duration_seconds,
                    "revision": summary.usage.revision,
                    "latest_change_at": summary.usage.latest_change_at,
                },
                "jobs": {
                    "total_jobs": summary.patterns.total_jobs,
                    "jobs_with_executions": summary.patterns.jobs_with_executions,
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
