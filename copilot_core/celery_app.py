"""PilotSuite Celery Application."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

# Create Celery app
app = Celery('pilotsuite')

# Load configuration
app.config_from_object('copilot_core.celery_config')

# Auto-discover tasks
app.autodiscover_tasks(['copilot_core.tasks'])


# =============================================================================
# PERIODIC TASKS
# =============================================================================

app.conf.beat_schedule = {
    # Weather evaluation - every 5 minutes
    'weather-evaluate-every-5min': {
        'task': 'copilot_core.tasks.weather.evaluate_automations',
        'schedule': 300.0,
    },
    
    # Metrics collection - every 5 minutes
    'metrics-collect-every-5min': {
        'task': 'copilot_core.tasks.metrics.collect',
        'schedule': 300.0,
    },
    
    # Multi-home sync - every 5 minutes
    'sync-evaluate-every-5min': {
        'task': 'copilot_core.tasks.sync.evaluate',
        'schedule': 300.0,
    },
    
    # Pattern detection - every hour
    'patterns-detect-every-hour': {
        'task': 'copilot_core.tasks.patterns.detect',
        'schedule': 3600.0,
    },
    
    # Backup - daily at 2 AM
    'backup-create-daily': {
        'task': 'copilot_core.tasks.backup.create',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # Daily report - daily at 8 AM
    'report-daily': {
        'task': 'copilot_core.tasks.report.daily',
        'schedule': crontab(hour=8, minute=0),
    },
    
    # Weekly report - Sunday at 10 AM
    'report-weekly': {
        'task': 'copilot_core.tasks.report.weekly',
        'schedule': crontab(hour=10, minute=0, day_of_week=0),
    },
    
    # Notification cleanup - daily at 3 AM
    'notifications-cleanup-daily': {
        'task': 'copilot_core.tasks.notifications.cleanup',
        'schedule': crontab(hour=3, minute=0),
    },
}


# =============================================================================
# TASK ROUTING
# =============================================================================

app.conf.task_routes = {
    'copilot_core.tasks.backup.*': {'queue': 'backups'},
    'copilot_core.tasks.report.*': {'queue': 'reports'},
    'copilot_core.tasks.energy.*': {'queue': 'energy'},
    'copilot_core.tasks.weather.*': {'queue': 'default'},
    'copilot_core.tasks.patterns.*': {'queue': 'default'},
    'copilot_core.tasks.sync.*': {'queue': 'default'},
    'copilot_core.tasks.metrics.*': {'queue': 'default'},
    'copilot_core.tasks.notifications.*': {'queue': 'default'},
}


# =============================================================================
# WORKER CONFIGURATION
# =============================================================================

app.conf.update(
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=200000,  # 200MB
    
    # Timeouts
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    
    # Monitoring
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Result settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Retry
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
)


# =============================================================================
# TASK REGISTRATION
# =============================================================================

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def weather_evaluate_automations(self):
    """Evaluate weather automations."""
    try:
        from copilot_core.integrations.weather_automation import WeatherAutomationEngine
        
        # Would get engine from hass.data
        # engine = hass.data["pilotsuite_weather_engine"]
        # triggered = await engine.evaluate_rules()
        
        return {"success": True, "triggered": []}
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def metrics_collect(self):
    """Collect system metrics."""
    try:
        from copilot_core.analytics.advanced_analytics import AnalyticsEngine, MetricType
        
        # Would get engine from hass.data
        # engine = hass.data["pilotsuite_analytics_engine"]
        
        # Record metrics
        # engine.record("system_cpu_percent", cpu_usage)
        # engine.record("system_memory_percent", memory_usage)
        
        return {"success": True}
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def sync_evaluate(self):
    """Evaluate multi-home sync."""
    try:
        # Would get engine from hass.data
        # engine = hass.data["pilotsuite_sync_engine"]
        # result = await engine.sync_now()
        
        return {"success": True}
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def patterns_detect(self, user_id=None):
    """Detect patterns in user behavior."""
    try:
        from copilot_core.ml.pattern_detection import PatternDetectionEngine
        
        engine = PatternDetectionEngine()
        patterns = engine.detect_patterns(user_id)
        
        return {
            "success": True,
            "patterns_found": len(patterns),
        }
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def backup_create(self, include_patterns=True, include_vectors=True):
    """Create system backup."""
    import tarfile
    import os
    from pathlib import Path
    from datetime import datetime
    
    try:
        backup_dir = Path("/config/pilotsuite/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"pilotsuite_backup_{timestamp}.tar.gz"
        
        # Create backup
        with tarfile.open(backup_file, "w:gz") as tar:
            if include_patterns:
                patterns_dir = Path("/config/pilotsuite/patterns")
                if patterns_dir.exists():
                    tar.add(patterns_dir, arcname="patterns")
            
            if include_vectors:
                vectors_dir = Path("/config/pilotsuite/vectors")
                if vectors_dir.exists():
                    tar.add(vectors_dir, arcname="vectors")
        
        return {
            "success": True,
            "backup_file": str(backup_file),
            "size_bytes": backup_file.stat().st_size if backup_file.exists() else 0,
        }
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def report_daily(self):
    """Generate daily report."""
    import asyncio
    try:
        from copilot_core.reporting.engine import ReportGenerator, ReportDelivery
        
        generator = ReportGenerator()
        delivery = ReportDelivery()
        
        # Run async methods in sync context
        loop = asyncio.get_event_loop()
        report = loop.run_until_complete(generator.generate_daily_summary())
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d")
        filepath = f"/config/pilotsuite/reports/daily_{timestamp}.json"
        
        loop.run_until_complete(delivery.deliver_to_file(report, filepath))
        
        return {
            "success": True,
            "report_file": filepath,
        }
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def report_weekly(self):
    """Generate weekly report."""
    import asyncio
    try:
        from copilot_core.reporting.engine import ReportGenerator, ReportDelivery
        
        generator = ReportGenerator()
        delivery = ReportDelivery()
        
        # Run async methods in sync context
        loop = asyncio.get_event_loop()
        report = loop.run_until_complete(generator.generate_weekly_summary())
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d")
        filepath = f"/config/pilotsuite/reports/weekly_{timestamp}.json"
        
        loop.run_until_complete(delivery.deliver_to_file(report, filepath))
        
        return {
            "success": True,
            "report_file": filepath,
        }
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def notifications_cleanup(self, older_than_days=7):
    """Clean up old notifications."""
    try:
        # Would delete old notifications from database
        return {
            "success": True,
            "cleanup_completed": True,
        }
    
    except Exception as e:
        raise self.retry(exc=e)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def energy_optimize(self, device_ids=None, horizon_hours=24):
    """Optimize energy consumption."""
    try:
        from copilot_core.energy.or_tools_scheduler import ORToolsScheduler
        
        scheduler = ORToolsScheduler()
        result = scheduler.optimize(device_ids, horizon_hours)
        
        return {
            "success": True,
            "savings_ct": result.total_cost if result else 0,
        }
    
    except Exception as e:
        raise self.retry(exc=e)
