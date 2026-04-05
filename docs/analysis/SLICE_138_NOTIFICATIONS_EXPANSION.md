# Slice 138: Notifications Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** notifications.py (145KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/notifications | ✅ List notifications |
| POST /api/v1/notifications | ✅ Create notification |
| DELETE /api/v1/notifications/<id> | ✅ Delete |

## Expansion Needed

1. **Notification Categories** — Group by type (alert, info, warning, action)
2. **Priority Queue** — Urgent vs. deferred notifications
3. **User Preferences** — Per-user notification settings
4. **Delivery Channels** — Push, email, SMS, in-app

## Decision

**Action:** Add categories + priority endpoints

**Priority:**
1. Notification categories
2. Priority queue
3. User preferences
4. Delivery channels

