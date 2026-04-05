# Slice 156: Jobs API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** jobs.py (14KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/jobs | ✅ List jobs |
| POST /api/v1/jobs | ✅ Create job |

## Expansion Needed

1. **Job Queue Management** — Queue inspection and control
2. **Job Retry** — Manual retry of failed jobs
3. **Job Cancellation** — Cancel pending/running jobs
4. **Job Analytics** — Throughput and failure tracking

## Decision

**Action:** Add queue + retry + cancel endpoints

**Priority:**
1. Job queue management
2. Job retry
3. Job cancellation
4. Job analytics

