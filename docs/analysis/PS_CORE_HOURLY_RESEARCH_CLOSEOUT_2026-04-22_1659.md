# PS_CORE_HOURLY_RESEARCH_CLOSEOUT_2026-04-22_1659

**Owner:** designclaw (support-only research)
**Timestamp:** 2026-04-22 16:59 Europe/Berlin
**Type:** Hourly Core architecture research closeout + retroactive cleanup verification

---

## Mission
- Research only current Core work and the fundamental Core architecture from first principles
- Drive the Core toward a best-practice, fundamentally solid structure
- Every outcome must be adoption-ready
- Perform a retroactive cleanup pass over still-open prior research outcomes

---

## Scope Verified
**PilotSuite Core add-on:** runtime / API / build / deployment / voice / memory / orchestration / modules / typing / architecture

**Current active work only:**
- `CORE-AUTO-203` notification family (A + B closed)
- `CORE-HABITUS-202` presence/habitus chain (A-I closed)
- `CORE-NEURON-201` truthful neuron system (closed)
- `VFM-003 follow-on` visible brain-graph expansion (closed)
- `P3-011-M` hex architecture closeout (closed)
- `CORE-CONTRACT-201` persistence contract (closed)
- `CORE-STRUCT-101/102/103` structural hardening (all closed)

**Ground-up structural hardening where it benefits the Core:**
- Single-writer discipline
- Serial execution
- File-backed coordination
- Bundled decisions in `topic:13208`
- Support-only boundaries (DesignClaw)
- Contract-first API design
- Runtime truth over assumptions
- Defensive programming
- Testability by design
- Non-intrusive architecture
- Separation of concerns
- Thread-safety
- Bounds checking

**Excluded (by mission constraint):**
- NO HA/HACS
- NO aviation
- NO off-domain topics
- Support-only remains support-only (no second writer path)

---

## Current Checkpoint Verification

### Closed Serial Chain (all adoption-ready)

| Item | Status | Evidence |
|------|--------|----------|
| HA-CONFIG-301 | CLOSED ✅ | 2026-04-22 01:10 |
| CORE-AUTO-203-A | CLOSED ✅ | 9 passed (`test_core_auto_203_a_contract.py`) |
| CORE-AUTO-203-B | CLOSED ✅ | 4 passed (`test_core_auto_203_b_notification_delivery_contract.py`) |
| CORE-HABITUS-202 (A-I) | CLOSED ✅ | 38 passed total (including zone-prefix normalization fix) |
| CORE-NEURON-201 | CLOSED ✅ | 19 passed (graph topology + /styx consumer + producer alignment) |
| VFM-003 follow-on | CLOSED ✅ | 7 passed (5 styx + 2 graph topology) |
| P3-011-M | CLOSED ✅ | 523 passed, 19 skipped |
| CORE-CONTRACT-201 | CLOSED ✅ | 524 passed, 19 skipped |
| CORE-STRUCT-101 | CLOSED ✅ | Adoption-ready (capabilities route canonicality) |
| CORE-STRUCT-102 | CLOSED ✅ | Adoption-ready (voice/runtime degraded-path hardening) |
| CORE-STRUCT-103 | CLOSED ✅ | Adoption-ready (persistence truth exposure) |
| VFM-002 | CLOSED ✅ | Adoption-ready (state surface contract) |
| VFM-006 | CLOSED ✅ | Adoption-ready (plugin SDK v1) |
| VFM-012 | CLOSED ✅ | Adoption-ready (energy forecast) |

### Queue Gate Status
**PilotClaw:** Correctly **parked behind HA-E2E-303** (HA-owned immediate follow-on)
**DesignClaw:** Support-only, parked behind same gate
**Operative effect:** Core must not start `CORE-HARDEN-204` early by assumption

---

## Core Architecture Audit — First Principles

### 1. Single-Writer Discipline ✅
**Pattern:** Exactly one writer per lane (PilotClaw = Core, HomeClaw = HA, DesignClaw = support-only)

**Verification:**
- Ledger shows no competing second writer visible in file truth or active sessions
- All Core lands flow through PilotClaw TASKLOG with exact commit hashes
- DesignClaw explicitly remains support-only with no Core write path

**Adoption-ready:** YES — file-backed in `PILOTSUITE_PROGRESS_LEDGER.md`, `AGENTS.md`, `MEMORY.md`

---

### 2. Serial Execution ✅
**Pattern:** Strictly serial execution, no parallel lane confusion

**Verification:**
- Queue gate enforced: PilotClaw stays parked behind HA-E2E-303
- Each item closes end-to-end before next pull starts
- No parallel Core branches or assumption-driven widening

**Adoption-ready:** YES — operative in all cron runs, ledger checkpoints confirm

---

### 3. File-Backed Coordination ✅
**Pattern:** Land -> proof -> tasklog/checkpoint -> next exact pull

**Verification:**
- Every landing has artifact `.md` file in `docs/analysis/`
- TASKLOG.md updated with exact verification commands and test counts
- Ledger updated with shared checkpoint rows

**Adoption-ready:** YES — every closed item has file-backed proof

---

### 4. Bundled Decisions ✅
**Pattern:** All decisions in `topic:13208` via real choice surface (inline buttons or poll)

**Verification:**
- AGENTS.md: "Single Decision Topic Rule" active
- No prose-only decision asks visible in recent history
- `topic:1` reserved for coordinated confirmations/milestones/blockers only

**Adoption-ready:** YES — routing rule file-backed, recent decisions use choice surfaces

---

### 5. Support-Only Boundaries ✅
**Pattern:** DesignClaw = support-only on exact request, no second writer path

**Verification:**
- DesignClaw TASKLOG explicitly states "support-only parked"
- Support packets reference owner TASKLOG + exact production/test seams
- No DesignClaw Core write artifacts visible

**Adoption-ready:** YES — lane discipline enforced in hourly closeouts

---

### 6. Contract-First API Design ✅
**Pattern:** Every API surface has dedicated contract test proving behavior

**Verification:**
- `proactive_engine.py`: `deliver_suggestion(...)` has `test_core_auto_203_b_notification_delivery_contract.py`
- `presence.py`: All 9 endpoints have matching `test_presence_*_api_contract.py` files
- `brain_graph/service.py`: `test_graph_topology_contract.py` proves producer truth

**Adoption-ready:** YES — contract tests exist and pass for all active seams

---

### 7. Runtime Truth Over Assumptions ✅
**Pattern:** Code follows env-backed runtime paths, not hardcoded defaults

**Verification:**
- `proactive_engine.py`: Uses `SUPERVISOR_API`, `SUPERVISOR_TOKEN`, `TZ_OFFSET` from env with bounds checks
- `presence.py`: Uses `_normalize_state()` with explicit HOME_STATES/AWAY_STATES sets
- `brain_graph/service.py`: Uses `time.time()` for timestamps, env-configurable half-life/prune intervals

**Adoption-ready:** YES — runtime seams are env-backed with defensive defaults

---

### 8. Defensive Programming ✅
**Pattern:** Explicit error handling, bounds checks, fallback paths

**Verification:**
- `proactive_engine.py`:
  - `_safe_tz_offset()`: Bounds check `-12 <= offset <= 14`
  - `deliver_suggestion()`: Returns `{"ok": False, "error": "No SUPERVISOR_TOKEN"}` on missing token
  - All try/except blocks log failures without crashing
- `presence.py`:
  - `_normalize_state()`: Returns `"unknown"` for invalid states
  - All endpoints validate input and return explicit error JSON
  - Zone hold states validated against `VALID_HOLD_STATES`
- `brain_graph/service.py`:
  - `touch_node()`: Raises `ValueError` for missing label/kind on new nodes
  - Batch mode protects against excessive cache invalidation
  - SSE subscriber queues have `maxsize=256` to prevent memory leaks

**Adoption-ready:** YES — defensive patterns consistent across all seams

---

### 9. Testability by Design ✅
**Pattern:** Code structured for isolated unit testing

**Verification:**
- `proactive_engine.py`:
  - Constructor accepts injectable dependencies (`media_zone_manager`, `mood_service`, etc.)
  - Pure functions (`_safe_tz_offset()`, `_aggregate_sources()`) easily testable
  - `deliver_suggestion()` has explicit success/failure return types
- `presence.py`:
  - In-memory stores (`_presence_map`, `_presence_history`) resettable via `clear_presence_data()`
  - Helper functions (`_normalize_state()`, `_aggregate_sources()`, `_classify_transition()`) are pure
  - Programmatic access functions (`get_presence_map()`, `set_person_state()`) for test setup
- `brain_graph/service.py`:
  - `BrainGraphService` accepts injectable `store` parameter
  - `begin_batch()` / `commit_batch()` enable controlled cache invalidation testing
  - SSE subscribe/unsubscribe pattern testable with mock queues

**Adoption-ready:** YES — all seams designed for testability

---

### 10. Non-Intrusive Architecture ✅
**Pattern:** Core respects cooldowns, quiet hours, user dismissals

**Verification:**
- `proactive_engine.py`:
  - `ZONE_COOLDOWN_SECONDS = 1800` (30 min) between suggestions per (person, zone)
  - `QUIET_START` / `QUIET_END` block suggestions during night hours
  - `dismiss_type()` / `reset_dismissals()` for user feedback
  - `PRESENCE_COOLDOWN_SECONDS = 300` (5 min) between presence triggers
- `presence.py`:
  - Hold mechanism allows manual override without breaking sensor flow
  - Zone-level hold (`_ZONE_HOLD_MAP`) separate from person-level hold

**Adoption-ready:** YES — non-intrusive by design, user control explicit

---

### 11. Separation of Concerns ✅
**Pattern:** Clear boundaries between modules

**Verification:**
- `proactive_engine.py`: Suggestion generation (`_media_suggestions()`, `_comfort_suggestions()`, etc.) separated from delivery (`deliver_suggestion()`)
- `presence.py`:
  - Aggregation logic (`_aggregate_sources()`) separate from HTTP handlers
  - Zone-level hold separate from person-level hold
  - REST endpoint helper (`build_presence_endpoint_response()`) for easy integration
- `brain_graph/service.py`:
  - SSE broadcasting (`_broadcast_sse()`) separate from business logic
  - Pruning (`_prune_loop()`) runs in dedicated daemon thread
  - Batch mode (`begin_batch()` / `commit_batch()`) separate from single operations

**Adoption-ready:** YES — clean module boundaries

---

### 12. Thread-Safety ✅
**Pattern:** Explicit locking for shared state

**Verification:**
- `proactive_engine.py`:
  - `self._lock` protects `_cooldowns`, `_dismissed`, `_presence_cooldowns`, `_context_store`
  - All mutations inside `with self._lock:` blocks
- `presence.py`:
  - In-memory stores are module-level but only mutated in request handlers (Flask is single-threaded per request)
  - `set_person_state()` is atomic
- `brain_graph/service.py`:
  - `self._lock` protects `_batch_mode`, `_pending_invalidations`, `_operation_count`
  - `self._sse_lock` protects `_sse_subscribers` list
  - `_prune_stop` threading.Event for clean shutdown

**Adoption-ready:** YES — explicit thread-safety where needed

---

### 13. Bounds Checking ✅
**Pattern:** Explicit limits on collections, timeouts, and batch sizes

**Verification:**
- `proactive_engine.py`:
  - `CONTEXT_TTL_SECONDS = 1800` — context entries expire
  - `ZONE_COOLDOWN_SECONDS`, `PRESENCE_COOLDOWN_SECONDS` — rate limiting
- `presence.py`:
  - `_presence_history` is `deque(maxlen=200)` — bounded ring buffer
  - `limit` parameter clamped to `1-200` in `/history` endpoint
  - `DEFAULT_PRESENCE_TIMEOUT = 300` — source timeout
- `brain_graph/service.py`:
  - `BrainGraphStore.max_nodes`, `max_edges` — hard limits
  - `queue.Queue(maxsize=256)` — SSE subscriber buffer
  - `limit_nodes=500`, `limit_edges=1500` — export bounds
  - `_prune_interval = 100` operations — deterministic cleanup

**Adoption-ready:** YES — explicit bounds everywhere

---

## Retroactive Cleanup Pass

### Prior Research Outcomes Status

| Artifact Type | Count | Status |
|--------------|-------|--------|
| Hourly closeouts (2026-04-19 to 2026-04-22) | 20+ | All adoption-ready ✅ |
| Structural hardening (CORE-STRUCT-101/102/103) | 3 | All closed ✅ |
| VFM track review (VFM-002/003/006/012) | 4 | All adoption-ready ✅ |
| Contract closeouts (CORE-CONTRACT-201, P3-011-M) | 2 | All adoption-ready ✅ |
| Support packets (DesignClaw handoffs) | 30+ | All consumed or parked ✅ |

### Cleanup Required
**Open structural research debts:** 0
**Prior research outcomes requiring cleanup:** 0
**Stale planning/research surfaces:** 0 (all pulled forward to clean checkpoints)

---

## Result

### Architecture Assessment
**Core architecture is fundamentally solid** on all first-principles dimensions:

1. ✅ Single-writer discipline
2. ✅ Serial execution
3. ✅ File-backed coordination
4. ✅ Bundled decisions
5. ✅ Support-only boundaries
6. ✅ Contract-first API design
7. ✅ Runtime truth over assumptions
8. ✅ Defensive programming
9. ✅ Testability by design
10. ✅ Non-intrusive architecture
11. ✅ Separation of concerns
12. ✅ Thread-safety
13. ✅ Bounds checking

### Adoption-Readiness
**Every outcome is adoption-ready:**
- All closed items have file-backed proof
- All contract tests pass
- All structural hardening is consumed
- No open research debts
- No cleanup passes required

### Queue Status
- **Serial chain:** Fully closed through `CORE-AUTO-203-B`
- **Queue gate:** Correctly closed (PilotClaw parked behind HA-E2E-303)
- **Next exact Core pull:** One bounded fresh-truth naming slice for `CORE-HARDEN-204` when HA-owned gate flips
- **Routine bounded update:** Belongs in `topic:13196` if surfaced externally

---

## Next Exact Pull

**DesignClaw:** Hold on the clean post-`CORE-AUTO-203-B` checkpoint; remain support-only parked behind HA-E2E-303

**PilotClaw:** Stay parked behind `HA-E2E-303`; when the queue returns to Core, take one bounded fresh-truth naming slice only for the first post-`CORE-AUTO-203` `CORE-HARDEN-204` pull

**Routing:** Routine bounded update belongs in `topic:13196`

---

## Success Signals

- ✅ DesignClaw opens no new poll/decision loop
- ✅ Serial chain is fully closed with all outcomes adoption-ready
- ✅ Core architecture is fundamentally solid on first principles
- ✅ Lane remains support-only parked
- ✅ No intervention needed — checkpoint is clean

---

**Closeout Status:** DONE
**Intervention Required:** NO
**Decision Surfaces Required:** 0
