# PS_CORE_HOURLY_RESEARCH_CLOSEOUT_2026-04-21_1955

**Timestamp:** 2026-04-21 19:55 Europe/Berlin  
**Lane:** DesignClaw (support-only)  
**Mission:** PilotSuite Core hourly research — STRICT CORE ADD-ON ONLY

---

## Executive Summary

**Status:** CLEAN CHECKPOINT — no intervention required

- **CORE-HABITUS-202 chain (A through H):** FULLY CLOSED ✅
- **Total tests on habitus/presence chain:** 15 passed (4+3+3+5+4+3+4+4)
- **Next exact Core pull:** `CORE-HABITUS-202-I` on `POST /api/v1/presence/check_timeouts`
- **Open structural research debts:** 0
- **Prior research outcomes requiring cleanup:** 0
- **All outcomes:** adoption-ready

---

## Core Architecture Audit (First Principles)

### Fundamental Structure — Verified Solid

The Core architecture demonstrates best-practice structural integrity across all dimensions:

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Single Writer** | ✅ Active | PilotClaw remains sole Core writer; DesignClaw support-only |
| **Serial Execution** | ✅ Active | One active pull at a time (CORE-HABITUS-202-I next) |
| **File-Backed Coordination** | ✅ Active | Ledger, TASKLOGs, and analysis docs carry all truth |
| **Bounded Pulls** | ✅ Active | Each slice has exact files, exact tests, exact verification |
| **Contract-First** | ✅ Active | All endpoints have dedicated proof rings before consumption |
| **Auth-Gated** | ✅ Active | All modifying endpoints require valid token (401 without) |
| **Error Honesty** | ✅ Active | 400 on missing params, 404 on unknown, 409 on conflicts |
| **No Parallel Drift** | ✅ Active | No second Core/HA/Meta paths opened |

### Core Add-On Architecture — Adoption-Ready Patterns

**1. Multi-Source Aggregation Pattern** (`presence.py`)
- Any-on rule: if ANY source reports "home", person is present
- Timeout-reset: activity resets presence timeout
- Hold-switch: manual override ignores sensor states
- **Status:** Fully implemented, tested, adoption-ready

**2. Zone-Level Hold Pattern** (`/zone/presence/<zone_id>/hold`)
- Separate hold map per zone (not per-person)
- States: `auto` / `force_on` / `force_off`
- HA AreaPresenceSensor integration ready
- **Status:** CORE-HABITUS-202-D closed (5 passed)

**3. Zone Presence State Ingestion** (`/zone/presence/<zone_id>/state`)
- HA aggregated presence → Core truth
- Throttled at source (30s max)
- Stored for Brain/Neuron consumption
- **Status:** CORE-HABITUS-202-C closed (3 passed)

**4. Presence History Ring Buffer**
- Bounded at 200 events (newest first)
- Event classification: `arrived` / `departed` / `zone_changed`
- Limit clamp on read (max 200)
- **Status:** CORE-HABITUS-202-F closed (3 passed)

**5. Hold with Expiration** (`POST /api/v1/presence/hold`)
- Optional `duration` for auto-expire
- Hold-driven history triggers
- Clear hold recomputes from sources
- **Status:** CORE-HABITUS-202-G (4 passed) + CORE-HABITUS-202-H (4 passed) closed

**6. Source Transparency** (`GET /api/v1/presence/sources`)
- Per-person source breakdown
- Hold state visible
- Aggregated state explicit
- **Status:** CORE-HABITUS-202-E closed (4 passed)

**7. Status Aggregation** (`GET /api/v1/presence/status`)
- Persons home/away lists
- Hold-active tracking
- Total counts
- **Status:** CORE-HABITUS-202-B closed (3 passed)

**8. LLM Context Builder** (`get_presence_context_for_llm()`)
- German-language presence summary
- Zone-aware for home persons
- Empty string when no persons tracked
- **Status:** Integrated, adoption-ready

---

## Serial Chain Verification

### CORE-HABITUS-202 Complete Chain

| Slice | Endpoint | Tests | Status | Artifact |
|-------|----------|-------|--------|----------|
| **A** | `GET /api/v1/habitus/zones` | 4 passed | ✅ | PS_CORE_SLICE_298 |
| **B** | `GET /api/v1/presence/status` | 3 passed | ✅ | PS_CORE_SLICE_299 |
| **C** | `POST /zone/presence/<zone_id>/state` | 3 passed | ✅ | PS_CORE_SLICE_300 |
| **D** | `POST /zone/presence/<zone_id>/hold` | 5 passed | ✅ | PS_CORE_SLICE_301 |
| **E** | `GET /api/v1/presence/sources` | 4 passed | ✅ | PS_CORE_SLICE_302 |
| **F** | `GET /api/v1/presence/history` | 3 passed | ✅ | PS_CORE_SLICE_303 |
| **G** | `POST /api/v1/presence/hold` | 4 passed | ✅ | PS_CORE_SLICE_304 |
| **H** | `DELETE /api/v1/presence/hold` | 4 passed | ✅ | PS_CORE_SLICE_305 |

**Total:** 30 tests passed across 8 slices  
**Chain integrity:** Clean end-to-end, no gaps

### Preceding Chain Context

- **HA-SURFACE-302** ✅ → HA consumer proof ring (179 passed)
- **CORE-NEURON-201** (A/B/C) ✅ → Graph topology truth (7 passed)
- **VFM-003 follow-on** ✅ → Styx consumer bind (5 + 2 passed)
- **P3-011-M** ✅ → Hex architecture (523 passed)
- **CORE-CONTRACT-201** (A-E) ✅ → Persistence contracts (524 passed)
- **CORE-STRUCT-101/102/103** ✅ → Structural hardening (all closed)

---

## Next Exact Pull: CORE-HABITUS-202-I

### Target
`POST /api/v1/presence/check_timeouts`

### Purpose
- Periodic timeout-check mechanism
- Handles timeout-reset logic
- Expires holds automatically
- Recomputes state when sources time out

### Expected Contract
- **401** without auth
- **200** with canonical response:
  ```json
  {
    "ok": true,
    "timed_out": ["person.alice"],
    "state_changed": true
  }
  ```
- No-op path when no timeouts
- Hold expiration triggers
- History events on timeout-driven state changes

### Required Files
- **Owner:** `addons/pilotsuite/app/copilot_core/api/v1/presence.py` (already has `check_timeouts` endpoint)
- **Test:** `tests/test_presence_check_timeouts_api_contract.py` (TO BE CREATED)
- **Analysis:** `PS_CORE_SLICE_306_CORE_HABITUS_202_I_PRESENCE_CHECK_TIMEOUTS_CONTRACT_2026-04-21.md`

### Verification Ring
```bash
cd /config/clawd/team/worktrees/pilotsuite-styx-core-current
/config/clawd/.venv_smoke_gate/bin/python -m py_compile addons/pilotsuite/app/copilot_core/api/v1/presence.py tests/test_presence_check_timeouts_api_contract.py
/config/clawd/.venv_smoke_gate/bin/python -m pytest -q tests/test_presence_check_timeouts_api_contract.py
```

### Guardrails
- One dedicated proof ring only
- No widening into automation/config
- No HA consumer binding yet (stays PilotClaw-owned)
- Checkpoint after landing before any follow-on

---

## Retroactive Cleanup Pass

### Prior Research Outcomes — All Adoption-Ready

| Track | Status | Tests | Notes |
|-------|--------|-------|-------|
| **VFM-002** (Voice command state) | ✅ Closed | 39 passed | HA consumer bound |
| **VFM-003** (Brain graph expansion) | ✅ Closed | 7 passed | Styx consumer bound |
| **VFM-006** (Solar surplus notify) | ✅ Closed | 2 passed | Contract proof |
| **VFM-012** (Automations caller) | ✅ Closed | 12 passed | Generator surface |
| **CORE-STRUCT-101** (Runtime/API) | ✅ Closed | Multiple | Route canonicality |
| **CORE-STRUCT-102** (Voice/Memory) | ✅ Closed | 27 passed | Degraded-path hardening |
| **CORE-STRUCT-103** (State/Persistence) | ✅ Closed | Multiple | Path alignment |
| **CORE-NEURON-201** (Truthful neuron system) | ✅ Closed | 16 passed | Producer/consumer alignment |
| **CORE-CONTRACT-201** (Persistence docs) | ✅ Closed | 524 passed | All 5 sub-slices |
| **P3-011** (Hex architecture) | ✅ Closed | 523 passed | Voice runtime seam |

### Stale Document Audit

**28 hourly closeout documents** exist in `docs/analysis/` — all are valid checkpoint artifacts documenting clean progression. No cleanup required.

**Handoff documents** in `team/shared/handoffs/` — all are consumed or still-relevant support packets. No cleanup required.

**No open research debts** — all structural, VFM, and architecture work is file-backed closed with passing tests.

---

## Operating Discipline — Verified

### Single Decision Topic Rule
- **Canonical topic:** `topic:13208` for all PilotSuite decisions
- **Choice surface rule:** Real Telegram choicebox/poll, never prose-only
- **Topic:1 usage:** Blocker/milestone/confirmation only

### Support Packet Freshness Rule
- Mandatory re-read of owner TASKLOG before any support packet
- Mandatory re-read of exact active production/test file
- No stale packet writes

### Internal Coordination Rule
- Agent-to-agent coordination stays internal
- One coordinated user-facing position
- No unaligned lane state exposed

### Start-Clear and Hand-in-Hand Rule
- Lean startup basis: `AGENTS.md` → `MEMORY.md` → `PILOTSUITE_PROGRESS_LEDGER.md` → own `TASKLOG.md`
- Then only exact extra file for active pull
- Proof → checkpoint → tasklog → next exact pull

---

## Recommendation

**No decision surface required.** The Core lane is on a clean, bounded, serial execution path with:

1. Complete habitus/presence chain (A-H) closed
2. Next pull already named (CORE-HABITUS-202-I)
3. Exact files and verification ring specified
4. No open research debts
5. No cleanup passes required

**DesignClaw remains support-only parked** until PilotClaw lands CORE-HABITUS-202-I or a real blocker appears.

---

## Closeout Checklist

- [x] Startup basis read (AGENTS.md → MEMORY.md → LEDGER → TASKLOG)
- [x] Core architecture audit from first principles
- [x] CORE-HABITUS-202 chain verified (A through H closed)
- [x] Next exact pull named (CORE-HABITUS-202-I)
- [x] Prior research outcomes reviewed (all adoption-ready)
- [x] Retroactive cleanup pass completed (0 items requiring cleanup)
- [x] Operating discipline verified (all rules active)
- [x] No decision surface needed (clean serial path)
- [x] DesignClaw remains support-only parked

---

**Next hourly closeout:** 2026-04-21 20:55 Europe/Berlin (or on CORE-HABITUS-202-I landing)
