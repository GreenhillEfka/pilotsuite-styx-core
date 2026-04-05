# Slice 162: Scenes API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** scenes.py (16KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/scenes | ✅ List scenes |
| POST /api/v1/scenes | ✅ Create scene |

## Expansion Needed

1. **Scene Activation** — Activate scenes with options
2. **Scene Scheduling** — Schedule scene activation
3. **Scene Variants** — Multiple variants per scene
4. **Scene Analytics** — Usage tracking

## Decision

**Action:** Add activation + scheduling + variants endpoints

**Priority:**
1. Scene activation
2. Scene scheduling
3. Scene variants
4. Scene analytics

