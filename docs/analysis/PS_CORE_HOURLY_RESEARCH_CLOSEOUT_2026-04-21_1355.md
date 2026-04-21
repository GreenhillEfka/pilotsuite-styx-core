# PS_CORE_HOURLY_RESEARCH_CLOSEOUT_2026-04-21_1355

**Run:** cron:ac6e6e2a-29b2-4f13-9f0a-0a14d32fdd91 (pilotsuite-hourly-state-of-art)
**Timestamp:** 2026-04-21 13:55 Europe/Berlin
**Lane:** DesignClaw (support-only)
**Mission:** Core research closeout + retroactive cleanup pass over prior research outcomes

## Startup Basis (binding)
1. `AGENTS.md` ✅ — routing discipline unchanged, one active pull only, routine Core updates in `topic:13196`
2. `MEMORY.md` ✅ — PilotClaw resumes serially behind shared file truth, no second Core writer
3. `/config/clawd/team/PILOTSUITE_PROGRESS_LEDGER.md` ✅ (Stand: 2026-04-21 13:39 — `HA-SURFACE-302` immediate, `CORE-HABITUS-202` queued/parked)
4. `/config/clawd/agents/designclaw/TASKLOG.md` ✅ (09:55 closeout confirmed, support-only parked)
5. `/config/clawd/agents/pilotclaw/TASKLOG.md` ✅ (13:39 — auth-gate sharpened, payload matrix prepared, still parked behind HA)

## Serial Chain Verification
| Item | Status | Evidence |
|------|--------|----------|
| HA-559 | CLOSED | Ledger 18:17, mobile-responsive Lovelace seam |
| F2.5-G3 | CLOSED | Ledger 18:34, `tests/test_solar_surplus_notify_contract.py` 2 passed |
| F7.1 | CLOSED | Ledger 19:19, `tests/test_plugins_api_contract.py` 2 passed |
| F8.5 | CLOSED | Ledger 20:49, `tests/test_mqtt_api_contract.py` 2 passed |
| CORE-STRUCT-102Q | CLOSED | Ledger, 27 passed |
| VFM-003 follow-on | CLOSED | Ledger, 7 passed (5 styx + 2 graph topology) |
| P3-011-M | CLOSED | Ledger, 523 passed, 19 skipped |
| CORE-CONTRACT-201-E | CLOSED | Ledger, 524 passed, 19 skipped |
| F10.5 / VFM-002 HA consumer binding | CLOSED | Ledger 00:34/01:19, 41 passed bounded Core verification |
| F7.2 plugin follow-on | CLOSED | Ledger 02:49, `tests/test_plugins_api_contract.py` 4 passed |
| Immediate serial package (3-item) | CLOSED | Ledger 03:34, all three consumed on fresh truth |
| **CORE-NEURON-201** | **CLOSED** | **Ledger 09:09, 7 passed graph-topology proof** |
| **CORE-NEURON-201-A** | **CLOSED** | **PilotClaw 06:34, 5 passed truthful family-mapping** |
| **CORE-NEURON-201-B** | **CLOSED** | **PilotClaw 07:19, 4 passed `/styx` consumer bind** |
| **CORE-NEURON-201-C** | **CLOSED** | **PilotClaw 09:09, 7 passed producer-source family alignment** |

## Current Active Core State (13:39 Ledger + PilotClaw TASKLOG)
**Shared queue truth:** `HA-SURFACE-302` remains the immediate HA-owned follow-on (HA lane head still `2026-04-20 23:52`).

**PilotClaw queued Core pull:** `CORE-HABITUS-202-A` is prepared but **parked** behind the single unlock gate (HA-SURFACE-302 closure).

**Preparation status (adoption-ready):**
| Aspect | Status | Details |
|--------|--------|---------|
| Auth gate | ✅ Pinned | Unauthenticated `GET /api/v1/habitus/zones` must return `401` with `error=unauthorized` + token message |
| Route matrix | ✅ Pinned | Default authenticated: `status=ok`, `total_zones=10`, canonical module-override ids, default metrics; `include_metrics=false` omits metrics; invalid `zone_type` keeps 400 |
| Proof ring | ✅ Pinned | `tests/test_habitus_zones_api_contract.py` — zone-list count, module-override ids (`light/motion/music/volume/tv/climate/camera`), metrics shape, 400 path |
| Exact files | ✅ Named | `addons/pilotsuite/app/copilot_core/api/v1/habitus_zones.py` + `tests/test_habitus_zones_api_contract.py` |

**Operative effect:** Core does not start early. The next cron can decide in one freshness read whether to stay parked or start the already-pinned habitus contract slice.

## Core Architecture Research (First Principles)
### Fundamental Core Structure Audit
Reviewed Core architecture against best-practice patterns:

| Pattern | Current State | Status |
|---------|---------------|--------|
| Single writer per lane | Enforced via Ledger + TASKLOG discipline | ✅ ADOPTION-READY |
| Strictly serial execution | Ledger-anchored, no parallel lane confusion | ✅ ADOPTION-READY |
| Proof -> checkpoint -> tasklog -> next pull | Operating rule in AGENTS.md + MEMORY.md | ✅ ADOPTION-READY |
| Shared startup basis | AGENTS.md -> MEMORY.md -> LEDGER -> TASKLOG -> exact pull file | ✅ ADOPTION-READY |
| Bundled decision topic | `topic:13208` with choicebox discipline | ✅ ADOPTION-READY |
| Support-only boundary | DesignClaw read-only, no second Core writer | ✅ ADOPTION-READY |
| File-backed coordination | All lanes align on Ledger truth, not chat | ✅ ADOPTION-READY |
| Active Core routing | `topic:13196` for routine bounded slice updates | ✅ ADOPTION-READY |

### Structural Hardening Review (CORE-STRUCT-101/102/103)
- **CORE-STRUCT-101** (Runtime/API hardening): Closed via capability surface closeout, repo-root FastAPI parity
- **CORE-STRUCT-102** (Voice/Memory hardening): Closed via 102Q closeout sweep (27 passed), all degraded-path packets landed
- **CORE-STRUCT-103** (State/Persistence hardening): Closed via shopping/DB path alignment, ready persistence visibility, REST compat surface

All structural hardening outcomes are **adoption-ready** with explicit verification rings and no open residuals.

### VFM Track Review
- **VFM-002** (Voice Command Router): Closed via state surface (`GET /api/v1/voice/command/state`), HA consumer binding ready
- **VFM-003 follow-on** (Brain Graph Expansion): Closed via `/styx` snapshot consumer bind + graph topology contract (7 passed)
- **VFM-006** (Boundary Cleanup): Closed via workflow decoupling, release-archive exclusion, tombstones, legacy doc delete
- **VFM-012** (Solar Surplus Automation): Closed via policy kernel, forecast adapters, reporting surface, API route, automations caller integration

All VFM outcomes are **adoption-ready** with contract tests and file-backed closeouts.

### Hexagonal Architecture (P3-011-M)
- Voice runtime access seam extracted (`runtime_access.py`)
- Command router construction moved out of HTTP adapter
- Command-flow port shaping for procedure orchestration
- Context-runtime seam consolidation (language/HA-assist/context-builder)
- Full hex boundary proof: 523 passed, 19 skipped

**Status:** ADOPTION-READY, no structural debts.

### Persistence Contract (CORE-CONTRACT-201-E)
- `/health` persistence surface for all three DBs (shopping, conversation, vector)
- Env-backed persistence path alignment
- Deep health authority boundary clarification
- REST compat persistence visibility

**Status:** ADOPTION-READY, 524 passed, 19 skipped.

### Neuron/Brain Graph Chain (CORE-NEURON-201)
- **CORE-NEURON-201-A** (06:34): Truthful family-mapping on `/api/v1/graph/topology` + `/api/v1/graph/snapshot.svg` — 5 passed ✅
- **CORE-NEURON-201-B** (07:19): `/styx` consumer bind for brain-family surface — 4 passed ✅
- **CORE-NEURON-201-C** (09:09): Producer-source family alignment in `brain_graph/service.py` — 7 passed ✅

**Status:** ADOPTION-READY, all three slices closed with explicit verification rings.

## Research Debt Status
- Open structural Core research debts: **0**
- Prior research outcomes requiring cleanup: **0** (retroactive cleanup pass completed in 09:55 closeout; no new stale artifacts since)
- New decision surfaces required: **0** (CORE-HABITUS-202 already named and pinned; no choice needed)
- Adoption-ready outcomes: **100%**

## Retroactive Cleanup Pass (13:55)
### Documents Reviewed Since 09:55 Closeout
No new research/planning documents created since 09:55 that require cleanup. The following were reviewed for freshness:

| Document | Status | Action |
|----------|--------|--------|
| `PILOTSUITE_PROGRESS_LEDGER.md` | ✅ Current | 13:39 entry confirms HA-SURFACE-302 immediate, CORE-HABITUS-202 parked |
| `PilotClaw TASKLOG.md` | ✅ Current | 13:39 auth-gate pinned, no drift |
| `PILOTSUITE_48H_TASKPLAN_2026-04-20.md` | ✅ Current | Bound order still valid, no revision needed |
| `PS_CORE_HOURLY_RESEARCH_CLOSEOUT_2026-04-21_0955.md` | ✅ Current | All claims still valid, no correction needed |

### No New Stale Artifacts
The 09:55 retroactive cleanup pass already pulled forward all stale planning/research surfaces to the clean post-`CORE-NEURON-201` checkpoint. No new stale artifacts have accumulated since then.

## Routing Discipline
- Decision topic: `topic:13208` (no new choice surface needed — CORE-HABITUS-202 already named and pinned)
- Topic 1: reserved for coordinated confirmations, real blockers, milestones only
- Active Core routing: `topic:13196` for routine bounded slice updates (Ledger 12:34)
- No routing drift, thread changes, or contradictory user-facing asks introduced

## Conclusion
- The serial chain through `CORE-NEURON-201` (A/B/C) remains fully closed with all outcomes adoption-ready.
- `CORE-HABITUS-202` is named as the first post-neuron Core pull, with `CORE-HABITUS-202-A` pinned to the exact habitus-zones ingress seam.
- The queued Core slice remains **parked** behind `HA-SURFACE-302` (HA lane head unchanged at `2026-04-20 23:52`).
- All preparation work (auth gate, route matrix, proof ring, exact files) is adoption-ready and file-backed.
- Core architecture remains fundamentally solid: single-writer, serial execution, file-backed coordination, bundled decisions, support-only boundaries.
- All structural hardening (CORE-STRUCT-101/102/103), VFM tracks, hexagonal architecture (P3-011-M), persistence contracts (CORE-CONTRACT-201-E), and neuron/brain graph chain (CORE-NEURON-201) remain adoption-ready.
- No new research debts have appeared since 09:55 closeout.
- No new retroactive cleanup is required.
- DesignClaw remains **support-only parked** on the clean checkpoint.
- No new poll/decision loop is opened.
- Next exact pull: hold on the named `CORE-HABITUS-202` handoff; only sharpen when PilotClaw starts the `CORE-HABITUS-202-A` pull or a real blocker appears.

## Files Touched
- This closeout note: `/config/clawd/team/worktrees/pilotsuite-styx-core-current/docs/analysis/PS_CORE_HOURLY_RESEARCH_CLOSEOUT_2026-04-21_1355.md`
