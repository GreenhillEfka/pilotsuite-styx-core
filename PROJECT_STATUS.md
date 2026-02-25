# PilotSuite - Production Status (2026-02-22)

Scope: dual-repo production audit (`pilotsuite-styx-core` + `pilotsuite-styx-ha`).

Release baseline for this status:
- Core add-on target: `7.7.16`
- HA integration target: `7.7.16`

## Executive summary
System is release-ready with validated critical communication loops and continuous guardrails.

Validated today:
- Core tests: `1959 passed, 1 skipped`.
- HA tests: `527 passed, 5 skipped`.
- Additional communication roundtrip integration test added and passing.
- CI now complemented by 15-minute production guard workflows in both repos.

Additional hardening completed:
- Core `agent/self-heal` endpoint for post-setup LLM remediation.
- Flat add-on option parsing (`conversation_*`) aligned with runtime status reporting.
- Cloud-style model request handling without cloud fallback routed to local model.

## What was audited
- Vision consistency (design intent vs runtime behavior).
- Module purpose and lifecycle for runtime-loaded modules.
- Forward path: HA events to Core ingest and graph/mining pipeline.
- Return path: candidate polling, repairs decisions, sync-back to Core.
- Configurability and runtime fallbacks.
- Dashboard/UX posture for operational clarity.

## Evidence-based verification
- Syntax checks (`py_compile`) pass for both repos.
- Core critical APIs validated by tests:
  - status/auth/events/full-flow/e2e pipeline.
- HA critical integrations validated by tests:
  - forwarder envelope behavior, candidate poller, repairs workflow, API compat.
- New full-flow integration test in HA validates:
  - N3 privacy-safe event envelope creation.
  - Candidate payload conversion for Repairs.
  - Accept/defer decision sync to Core candidate endpoint.

## Module implementation status
Core:
- Service initialization: resilient (`try/except` isolation in `core_setup.py`).
- Brain graph + habitus + candidates + mood + neurons: active and test-covered.
- Runtime persistence fallbacks for non-writable `/data`: implemented for key stores.

HA integration:
- Runtime module registry and lifecycle orchestration: active.
- 31 runtime modules loaded by default integration setup.
- Repairs-based governance loop and Core sync-back: active.

## Configurability posture
- Zero-config path exists for fast onboarding.
- Advanced options cover host/port/token, zones, features, and tuning knobs.
- Production safety options present through module gating + decision workflows.

## UX posture (state of the art criteria)
Current implementation meets project-level operational UX criteria:
- clear health/status visibility,
- recommendation inbox with explicit decisions,
- explainable recommendation data exposure,
- dashboard/card surfaces for mood/neurons/habitus,
- mobile-safe responsive behavior in ingress dashboard.

## Remaining known risks
- Full live HA runtime behavior still depends on environment-specific entities/devices.
- Scheduled production guards are quality loops, not autonomous feature development.

## Continuous hardening setup
Added in both repos:
- `.github/workflows/production-guard.yml`
- Trigger cadence: every 15 minutes (`cron: "*/15 * * * *"`)
- Purpose: fast detection of regressions on critical paths.

## Release gate
Production release is permitted when all of the following hold:
- local critical tests green,
- main CI green,
- production-guard workflow green,
- versions/changelogs/docs synchronized across both repos.
