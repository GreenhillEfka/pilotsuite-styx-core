

# ── SLICE 156: Jobs API Expansion ─────────────────────────────────
from flask import Blueprint

bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@bp.get("/queue")
def jobs_queue():
    """Get job queue status.
    
    Returns:
    - pending: Count of pending jobs
    - running: Count of running jobs
    - failed: Count of failed jobs
    - completed: Count of completed jobs (last 24h)
    """
    from copilot_core.jobs.manager import get_jobs_manager
    
    try:
        manager = get_jobs_manager()
        queue = manager.get_queue_status()
    except Exception as e:
        _LOGGER.warning("Failed to get job queue status: %s", e)
        queue = {
            "pending": 0,
            "running": 0,
            "failed": 0,
            "completed": 0
        }
    
    return jsonify({
        "ok": True,
        "queue": queue,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@bp.get("/queue/jobs")
def jobs_queue_list():
    """List jobs in queue by status.
    
    Query params:
    - status: pending|running|failed|completed (default: pending)
    - limit: Max jobs (default 50)
    """
    from copilot_core.jobs.manager import get_jobs_manager
    
    status = request.args.get("status", "pending")
    
    try:
        limit = int(request.args.get("limit", "50"))
    except (ValueError, TypeError):
        limit = 50
    
    limit = max(1, min(limit, 200))
    
    try:
        manager = get_jobs_manager()
        jobs = manager.list_jobs_by_status(status=status, limit=limit)
    except Exception as e:
        _LOGGER.warning("Failed to list queue jobs: %s", e)
        jobs = []
    
    return jsonify({
        "ok": True,
        "jobs": jobs,
        "count": len(jobs),
        "status": status,
        "limit": limit
    })


@bp.post("/<job_id>/retry")
def jobs_retry(job_id):
    """Retry a failed job.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("RETRY_JOB", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.jobs.manager import get_jobs_manager
    
    try:
        manager = get_jobs_manager()
        result = manager.retry_job(job_id=job_id)
        success = result.get("success", False)
        new_job_id = result.get("new_job_id")
    except Exception as e:
        _LOGGER.warning("Failed to retry job: %s", e)
        success = False
        new_job_id = None
    
    return jsonify({
        "ok": success,
        "job_id": job_id,
        "new_job_id": new_job_id
    })


@bp.post("/<job_id>/cancel")
def jobs_cancel(job_id):
    """Cancel a pending or running job.
    
    Requires admin token.
    """
    auth_error = _require_admin_mutation("CANCEL_JOB", "Admin token required")
    if auth_error:
        return auth_error
    
    from copilot_core.jobs.manager import get_jobs_manager
    
    try:
        manager = get_jobs_manager()
        result = manager.cancel_job(job_id=job_id)
        success = result.get("success", False)
    except Exception as e:
        _LOGGER.warning("Failed to cancel job: %s", e)
        success = False
    
    return jsonify({
        "ok": success,
        "job_id": job_id
    })


@bp.get("/analytics")
def jobs_analytics():
    """Get job processing analytics.
    
    Query params:
    - days: Days to analyze (default 7)
    """
    from copilot_core.jobs.manager import get_jobs_manager
    
    try:
        days = int(request.args.get("days", "7"))
    except (ValueError, TypeError):
        days = 7
    
    days = max(1, min(days, 90))
    
    try:
        manager = get_jobs_manager()
        analytics = manager.get_analytics(days=days)
    except Exception as e:
        _LOGGER.warning("Failed to get job analytics: %s", e)
        analytics = {
            "total_jobs": 0,
            "successful": 0,
            "failed": 0,
            "avg_duration_seconds": 0.0,
            "throughput_per_hour": 0.0
        }
    
    return jsonify({
        "ok": True,
        "analytics": analytics,
        "days": days,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
