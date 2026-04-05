# Slice 151: Backup API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** backup.py (10KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/backup | ✅ List backups |
| POST /api/v1/backup | ✅ Create backup |

## Expansion Needed

1. **Backup Scheduling** — Automated backup schedules
2. **Backup Restore** — Restore from backup
3. **Backup Verification** — Verify backup integrity
4. **Backup Export** — Export to external storage

## Decision

**Action:** Add scheduling + restore endpoints

**Priority:**
1. Backup scheduling
2. Backup restore
3. Backup verification
4. Backup export

