# Slice 147: Config API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** config.py (20KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/config | ✅ Get config |
| PUT /api/v1/config | ✅ Update config |

## Expansion Needed

1. **Config Validation** — Validate config before apply
2. **Config History** — Track config changes over time
3. **Config Rollback** — Revert to previous config version
4. **Config Diff** — Show differences between versions

## Decision

**Action:** Add validation + history endpoints

**Priority:**
1. Config validation
2. Config history
3. Config rollback
4. Config diff

