# Slice 167: Floor Plan API Expansion

**Status:** Analyzed (2026-04-05)
**Basis:** floorplan.py (5KB)

## Current State

| Endpoint | Status |
|----------|--------|
| GET /api/v1/floorplan | ✅ List floor plans |

## Expansion Needed

1. **Floor Plan Upload** — Upload floor plan images
2. **Floor Plan Zones** — Map zones to floor plan coordinates
3. **Floor Plan Entities** — Place entities on floor plan
4. **Floor Plan Export** — Export floor plan with overlays

## Decision

**Action:** Add upload + zones + entities + export endpoints

**Priority:**
1. Floor plan upload
2. Floor plan zones mapping
3. Floor plan entities placement
4. Floor plan export

