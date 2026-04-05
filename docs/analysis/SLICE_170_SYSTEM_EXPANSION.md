# Slice 170: System API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** system.py (18KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/system/info | ✅ System info |
| GET /api/v1/system/status | ✅ System status |

## Expansion Needed

1. **System Restart** — Controlled restart endpoints
2. **System Updates** — Update check/apply endpoints
3. **System Logs** — Log access and download
4. **System Diagnostics** — Full diagnostic bundle

## Decision

**Action:** Add restart + updates + logs + diagnostics endpoints

**Priority:**
1. System restart controls
2. System update management
3. System log access
4. System diagnostics bundle

