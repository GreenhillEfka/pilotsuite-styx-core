# Core Commit Prep — 2026-03-27

## Status
**Historical / superseded artifact.**

Dieses Dokument beschreibt eine frühere Commit-/Stage-Gruppierung aus der Core-Recovery-Phase.
Es ist **nicht mehr** die aktuelle operative Review-/Release-Prep-Anleitung.

## Boundary
- Repo/Dev only
- kein Release
- kein Install
- kein Live-Test

## Why this doc is historical now
Die ursprünglich hier geplanten Commit-Gruppen sind inzwischen in der Core-Lane materialisiert und von neueren Release-Prep-/Governance-Surfaces überholt worden.

Spätere, relevante Milestones oberhalb dieser frühen Commit-Prep-Phase sind u. a.:
- `3e135e21` — `feat(core): harden optional blueprints and proposal handoffs`
- `c7a88558` — `docs(core): refresh release prep after blueprint hardening milestone`
- `f5d0db99` — `docs(core): add release queue status and manifest drift note`
- `59a212bc` — `fix(core): make strict release gate workspace-exact`
- `249fdeb2` — `docs(core): refresh reviewer and ha handoff surfaces`

## Original intent (preserved for auditability)
Die frühere Absicht dieses Dokuments war:
1. funktionale Truth-Chain-Änderungen getrennt zu committen
2. Contract-/Regression-Evidence als eigenen Block zu schneiden
3. Review-/Handoff-/RC-Prep-Dokumente separat zu bündeln

Das war sinnvoll für die frühe Builder-Phase, ist aber **nicht** mehr der richtige operative Einstiegspunkt.

## Current authoritative surfaces instead
Für die aktuelle Review-/Releaser-/Governance-Arbeit gelten stattdessen diese Artefakte als maßgeblich:
- `docs/CORE_15_2_0_RELEASER_PREP_POINTER_2026-03-27.md`
- `docs/CORE_RC_PREP_2026-03-27.md`
- `docs/CORE_REVIEW_PACKET_2026-03-27.md`
- `docs/CORE_RELEASE_INPUT_2026-03-27.md`
- `docs/CORE_RELEASE_QUEUE_STATUS_2026-03-28.md`
- `docs/CORE_RELEASE_GOVERNANCE_CHECKLIST_2026-03-28.md`
- `docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md`

## Current authoritative commands instead
- `./scripts/run_core_contract_bundle.sh`
- `./scripts/check_15_2_0_releaser_pointers.sh`
- `./scripts/check_15_2_0_sync_anchor_consistency.sh`
- `./scripts/check_15_2_0_release_gate.sh`

## Release governance reminder
Vor jedem echten Releaseversuch gilt strikt:
1. `mache v15.2.0`
2. **5 Minuten warten**
3. Release-Lock beachten
4. `./scripts/check_15_2_0_release_gate.sh` erneut grün

## Exact next step
- Für aktuelle Builder-/Reviewer-/Releaser-Arbeit dieses Dokument **nicht** als Primärquelle verwenden.
- Stattdessen immer vom Releaser-Prep-Pointer + Queue/Governance/Gate-Surfaces ausgehen.
