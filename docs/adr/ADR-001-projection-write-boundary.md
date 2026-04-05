# ADR-001: Projection-Write Boundary (Core↔HA)

**Status:** Accepted (2026-04-05)  
**Owner:** PilotSuite Core Team  
**Relevance:** All Core + HA/HACS development  
**Canonical Location:** `pilotsuite-styx-core-current/docs/adr/ADR-001-projection-write-boundary.md`  
**Mirror:** `/config/clawd/team/shared/ADR-001-projection-write-boundary.md`

---

## Context

PilotSuite consists of two distinct runtime layers:

1. **Core Layer** (`pilotsuite-styx-core`)
   - Semantic truth engine
   - First-class module runtime
   - Brain/neuron/habitus reasoning layer
   - Policy engine
   - Explanation engine
   - RAG/chat reasoning surface

2. **HA/HACS Layer** (`pilotsuite-styx-ha`)
   - Raw runtime shell (Home Assistant)
   - Device/entity/area collection layer
   - Execution adapter
   - HA-native projection layer

Historically, the boundary between these layers was implicit. This led to:
- Occasional HA-side writes to Core state
- Unclear ownership of truth vs. projection
- Contract drift between layers

---

## Decision

**HA/HACS cannot write to Core truth.**

### Rules

1. **Core Truth is Write-Once (by Core only)**
   - All normalized semantic state lives in Core
   - Only Core APIs can mutate truth stores
   - HA/HACS has **read + subscribe** access only

2. **HA/HACS is Projection-Only**
   - HA receives Core state via sync endpoints
   - HA projects Core truth onto HA entities
   - HA can write HA-local config/attrs (not Core truth)
   - HA sends events/intents **to** Core for processing

3. **Event Flow is Unidirectional**
   ```
   HA Devices/Entities → HA Events → Core Ingest → Core Truth
   Core Truth → Core Read Models → HA Sync → HA Projections
   ```

4. **Contract Boundaries are Enforced**
   - Core↔HA communication via explicit APIs only
   - No direct database/file access across boundary
   - All cross-boundary data validated (Pydantic v2)
   - Contract inventory auto-check on commits (PS-151-Drift-Guard)

---

## Consequences

### Positive
- Clear ownership of truth vs. projection
- Prevents accidental Core state corruption from HA side
- Enables independent Core/HA evolution
- Contract drift detected early (build failure, not warning)

### Constraints
- HA cannot "quick fix" Core state directly
- All state changes must flow through Core APIs
- Requires explicit sync patterns for HA projections

### Migration
- Existing HA-side writes to Core state must be refactored
- Use Core sync endpoints (`/api/v1/zone-truth/sync/*`) for HA updates
- Audit current HA code for direct Core DB/file access

---

## Compliance

### Pre-Commit Checks
- Core: `scripts/contract_inventory_check.py` (this ADR + OpenAPI parity)
- HA: `scripts/ps_ha_projection_check.py` (no Core truth writes)

### Runtime Guards
- Core APIs validate all incoming HA events
- HA sync endpoints are read-only from HA perspective
- Audit logging for cross-boundary operations

---

## References

- `/config/clawd/team/PILOTSUITE_EXECUTION_FOUNDATION.md` — Core/HA lane separation
- `/config/clawd/team/worktrees/pilotsuite-styx-core-current/docs/HA_CORE_INGEST_CONTRACT.md`
- PS-151-Drift-Guard pattern (HA worktree)
- Microsoft AutoGen v2 boundary patterns
- Temporal workflow isolation patterns

---

**Amendment History:**
- 2026-04-05: Initial ADR (Orakel, PilotSuite Core Team)
