# H1 Truth Map — PilotSuite Core

## Summary
- Active worktree truth: `/config/clawd/team/worktrees/pilotsuite-styx-core-current`
- Runtime API tree Python files: **98**
- Repo-level API tree Python files: **18**
- Central blueprint config entries: **98** core + **3** external
- Runtime blueprint imports: **19**
- `docs/openapi.yaml` path count: **573**
- `copilot_core/docs/openapi.yaml` path count: **49**

## Canonical Truth Decision
- Primary API/runtime truth is the active Core worktree plus runtime wiring under `copilot_core/rootfs/usr/src/app/copilot_core/...`.
- Repo-level `copilot_core/api/v1` is not sufficient as sole truth source.
- `docs/API_REFERENCE.md` and `docs/API_COMPLETE.md` are reference-only, not contract truth.

## Runtime Wiring Validity
- `core_setup.py` compiles: **YES**

## Config vs Runtime Diffs
- In config, not imported by runtime blueprint: **80** modules
- In runtime blueprint imports, not in config: **1** modules

## Blockers
- **HIGH** truth_split: runtime API tree is much larger than repo-level API tree; runtime tree must be treated as primary wiring surface (`/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/copilot_core/api/v1`)
- **MEDIUM** documentation: API_REFERENCE.md explicitly marks itself as legacy/partially outdated (`/config/clawd/team/worktrees/pilotsuite-styx-core-current/docs/API_REFERENCE.md`)
- **MEDIUM** documentation: API_COMPLETE.md explicitly marks itself as legacy/historical (`/config/clawd/team/worktrees/pilotsuite-styx-core-current/docs/API_COMPLETE.md`)

## Recommendation
1. Treat H1 as verified truth capture complete only after this report is generated and reviewed.
2. Fix runtime wiring blocker(s) before claiming integrated iteration stability.
3. Use this report to drive H2 blueprint/OpenAPI reconciliation.

