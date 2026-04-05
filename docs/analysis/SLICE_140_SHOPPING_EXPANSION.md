# Slice 140: Shopping-List Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** shopping.py (16KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/shopping/list | ✅ Get list |
| POST /api/v1/shopping/item | ✅ Add item |
| DELETE /api/v1/shopping/item | ✅ Remove item |

## Expansion Needed

1. **Smart Suggestions** — ML-based item predictions
2. **Price Tracking** — Track item prices across stores
3. **Inventory Integration** — Sync with pantry/fridge sensors
4. **Recipe Integration** — Auto-add recipe ingredients

## Decision

**Action:** Add suggestions + price tracking endpoints

**Priority:**
1. Smart suggestions
2. Price tracking
3. Inventory sync
4. Recipe integration

