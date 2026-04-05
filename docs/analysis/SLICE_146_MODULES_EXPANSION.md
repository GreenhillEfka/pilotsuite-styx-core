# Slice 146: Modules API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** modules.py (45KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/modules | ✅ List modules |
| GET /api/v1/modules/<id> | ✅ Get module |
| POST /api/v1/modules | ✅ Create module |

## Expansion Needed

1. **Module Health** — Per-module health status
2. **Module Dependencies** — Dependency graph
3. **Module Metrics** — Performance per module
4. **Module Lifecycle** — Start/stop/restart controls

## Decision

**Action:** Add health + dependencies endpoints

**Priority:**
1. Module health
2. Module dependencies
3. Module metrics
4. Module lifecycle

