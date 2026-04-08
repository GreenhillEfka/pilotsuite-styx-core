# Monitoring & Metrics for PilotSuite Styx Core

Production-ready Prometheus monitoring implementation with comprehensive health checks and alerting.

## Overview

This package provides:

- **Prometheus-compatible metrics** (`/api/v1/metrics`)
- **Extended health checks** (`/api/v1/health`)
- **Readiness/Liveness probes** (`/api/v1/ready`, `/api/v1/live`)
- **Alert rules** for critical thresholds

## Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/metrics` | GET | Prometheus metrics (text format) | No |
| `/api/v1/metrics/summary` | GET | Human-readable metrics summary (JSON) | Yes |
| `/api/v1/health` | GET | Extended health check | No |
| `/api/v1/health?full=true` | GET | Full health check (includes external services) | No |
| `/api/v1/ready` | GET | Readiness probe | No |
| `/api/v1/live` | GET | Liveness probe | No |

## Metrics Collected

### HTTP Request Metrics
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_total` - Total request counter (by method, endpoint, status)
- `http_requests_in_progress` - Current in-flight requests

### System Metrics
- `system_cpu_usage_percent` - CPU usage percentage
- `system_memory_usage_bytes` - Memory usage in bytes
- `system_memory_usage_percent` - Memory usage percentage
- `system_disk_usage_percent` - Disk usage percentage

### Cache Metrics
- `cache_hits_total` - Total cache hits
- `cache_misses_total` - Total cache misses
- `cache_size_entries` - Current cache size
- `cache_hit_ratio` - Cache hit ratio (0.0 to 1.0)

### Connection Pool Metrics
- `connection_pool_size` - Total pool size
- `connection_pool_checked_out` - Connections in use
- `connection_pool_available` - Available connections
- `connection_pool_wait_seconds` - Time waiting for connection

### LLM API Metrics
- `llm_requests_total` - LLM API request counter
- `llm_tokens_total` - Token usage (prompt/completion)
- `llm_request_duration_seconds` - LLM API latency

### Home Assistant Metrics
- `homeassistant_requests_total` - HA API request counter
- `homeassistant_websocket_connections` - Active WS connections

### Background Task Metrics
- `background_tasks_running` - Currently running tasks
- `background_task_duration_seconds` - Task execution time

## Usage

### Recording Metrics

```python
from copilot_core.monitoring import get_metrics_collector, track_request_latency

# Using decorator
@track_request_latency
def my_endpoint():
    return {"status": "ok"}

# Manual recording
metrics = get_metrics_collector()
metrics.record_request("GET", "/api/v1/test", 200, 0.05)

# Cache metrics
metrics.record_cache_hit("default")
metrics.record_cache_miss("default")
metrics.set_cache_size(150, "default")

# Connection pool metrics
metrics.set_connection_pool_metrics(
    pool_name="ha_pool",
    size=10,
    checked_out=3,
    available=7,
)
```

### Health Checks

```python
from copilot_core.monitoring import get_health_checker

checker = get_health_checker()

# Quick health check (system + dependencies only)
health = await checker.get_quick_health()

# Full health check (includes external services)
health = await checker.full_health_check()

# Response format:
# {
#     "status": "healthy|degraded|unhealthy",
#     "timestamp": 1234567890.0,
#     "duration_ms": 45.2,
#     "components": {
#         "system": {...},
#         "dependencies": {...},
#         "modules": {...},
#         "storage": {...},
#         "services": {...}
#     }
# }
```

### Alert Evaluation

```python
from copilot_core.monitoring import get_alert_evaluator

evaluator = get_alert_evaluator()

# Evaluate all alerts with current metrics
alerts = await evaluator.evaluate_all(
    cpu_percent=85,
    memory_percent=70,
    disk_percent=60,
    error_rate=0.02,
    latency_p95=0.3,
    latency_p99=1.5,
    cache_hit_ratio=0.85,
)

# Response format:
# {
#     "status": "healthy|warning|critical",
#     "timestamp": 1234567890.0,
#     "firing_count": 2,
#     "firing_alerts": [...],
#     "all_alerts": [...]
# }
```

### Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'pilotsuite-styx-core'
    static_configs:
      - targets: ['styx-core:8909']
    metrics_path: '/api/v1/metrics'
    scrape_interval: 15s
```

### Alert Rules

Generate Prometheus alert rules YAML:

```python
from copilot_core.monitoring import get_alert_rules_yaml

yaml_config = get_alert_rules_yaml()
# Save to alerts.yml and include in Prometheus config
```

Or use the pre-defined rules in `alerts.py` directly in your Prometheus configuration.

## Alert Thresholds

| Alert | Threshold | Severity | Duration |
|-------|-----------|----------|----------|
| High CPU Usage | >90% | Warning | 5m |
| Critical CPU Usage | >95% | Critical | 2m |
| High Memory Usage | >85% | Warning | 5m |
| Critical Memory Usage | >95% | Critical | 2m |
| High Disk Usage | >80% | Warning | 10m |
| Critical Disk Usage | >95% | Critical | 5m |
| High Request Latency (P95) | >500ms | Warning | 5m |
| Critical Request Latency (P99) | >2s | Critical | 5m |
| High Error Rate | >5% | Critical | 5m |
| Low Cache Hit Ratio | <50% | Warning | 10m |
| Connection Pool Exhausted | 0 available | Critical | 2m |
| LLM High Error Rate | >10% | Critical | 5m |

## Integration with Grafana

Example dashboard queries:

```promql
# Request rate
rate(http_requests_total[5m])

# Error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Cache hit ratio
cache_hit_ratio

# Connection pool utilization
connection_pool_checked_out / connection_pool_size
```

## Files

- `metrics.py` - Prometheus metrics collector and decorators
- `health.py` - Comprehensive health check service
- `alerts.py` - Alert rules and evaluation logic
- `__init__.py` - Package exports
- `README.md` - This documentation

## Dependencies

- `prometheus_client` - Prometheus Python client
- `psutil` - System metrics (CPU, memory, disk)
- `aiohttp` - Async HTTP for service health checks
- `pyyaml` - YAML generation for alert rules (optional)

Install:
```bash
pip install prometheus_client psutil aiohttp pyyaml
```
