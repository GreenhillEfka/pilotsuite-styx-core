# Slice 172: Services API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** services.py (15KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/services | ✅ List services |
| POST /api/v1/services/<id>/call | ✅ Call service |

## Expansion Needed

1. **Service Registry** — Full service registry with metadata
2. **Service Testing** — Test service calls without execution
3. **Service History** — Track service call history
4. **Service Analytics** — Usage patterns, popular services

## Decision

**Action:** Add registry + testing + history + analytics endpoints

**Priority:**
1. Service registry
2. Service testing
3. Service history
4. Service analytics

