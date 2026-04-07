# PilotSuite Celery Worker Configuration

# Celery Configuration
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'

# Task Settings
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'Europe/Berlin'
enable_utc = True

# Performance
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 1000
worker_concurrency = 4

# Timeouts
task_time_limit = 300  # 5 minutes
task_soft_time_limit = 240  # 4 minutes

# Retry
broker_connection_retry_on_startup = True
broker_connection_max_retries = 10

# Monitoring
task_track_started = True
worker_send_task_events = True
task_send_sent_event = True

# Rate Limiting
worker_max_memory_per_child = 200000  # 200MB

# Scheduled Tasks (Celery Beat)
beat_schedule = {
    # Every 5 minutes
    'weather-evaluate': {
        'task': 'pilotsuite.tasks.weather.evaluate',
        'schedule': 300.0,
    },
    'metrics-collect': {
        'task': 'pilotsuite.tasks.metrics.collect',
        'schedule': 300.0,
    },
    'sync-evaluate': {
        'task': 'pilotsuite.tasks.sync.evaluate',
        'schedule': 300.0,
    },
    
    # Every hour
    'patterns-detect': {
        'task': 'pilotsuite.tasks.patterns.detect',
        'schedule': 3600.0,
    },
    
    # Every day at 2 AM
    'backup-create': {
        'task': 'pilotsuite.tasks.backup.create',
        'schedule': 7200.0,  # 2 AM UTC = 3 AM Berlin
    },
    
    # Every day at 8 AM
    'report-daily': {
        'task': 'pilotsuite.tasks.report.daily',
        'schedule': 28800.0,  # 8 AM UTC = 9 AM Berlin
    },
    
    # Every week on Sunday at 10 AM
    'report-weekly': {
        'task': 'pilotsuite.tasks.report.weekly',
        'schedule': 604800.0,  # 7 days
    },
}

# Task Routes
task_routes = {
    'pilotsuite.tasks.backup.*': {'queue': 'backups'},
    'pilotsuite.tasks.report.*': {'queue': 'reports'},
    'pilotsuite.tasks.energy.*': {'queue': 'energy'},
}

# Queue Definitions
task_queues = {
    'celery': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'backups': {
        'exchange': 'backups',
        'routing_key': 'backups',
    },
    'reports': {
        'exchange': 'reports',
        'routing_key': 'reports',
    },
    'energy': {
        'exchange': 'energy',
        'routing_key': 'energy',
    },
}

# Worker Configuration
worker_hijack_root_logger = False
worker_log_level = 'INFO'
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(task_name)s[%(task_id)s]: %(message)s'

# Result Settings
result_expires = 3600  # 1 hour
result_persistent = True

# Event Settings
event_queue_expires = 60.0
event_queue_ttl = 60.0
