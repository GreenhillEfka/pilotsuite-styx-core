# Slice 171: Ping API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** ping.py (3KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/ping | ✅ Health ping |

## Expansion Needed

1. **Ping Diagnostics** — Extended ping with component health
2. **Ping Latency** — Response time tracking
3. **Ping History** — Historical ping data
4. **Ping Alerts** — Threshold-based alerting

## Decision

**Action:** Add diagnostics + latency + history endpoints

**Priority:**
1. Ping diagnostics
2. Ping latency tracking
3. Ping history
4. Ping alerts

