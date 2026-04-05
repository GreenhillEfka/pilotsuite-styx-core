# Slice 144: Metrics API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** metrics.py (9KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/metrics | ✅ System metrics |
| GET /api/v1/metrics/performance | ✅ Performance metrics |

## Expansion Needed

1. **Custom Metrics** — User-defined metric tracking
2. **Metric Alerts** — Threshold-based alerting
3. **Metric Aggregation** — Time-based aggregations (avg, min, max, p95)
4. **Metric Export** — Export to external systems (Prometheus, etc.)

## Decision

**Action:** Add custom metrics + aggregation endpoints

**Priority:**
1. Custom metrics
2. Metric aggregation
3. Metric alerts
4. Metric export

