# Core GitHub Release Notes Input — 2026-03-27

## Purpose
Repo-lokaler Draft für GitHub-Release-Notes / changelog bullets.

**Non-claims:**
- kein Release geschnitten
- kein Tag erstellt
- kein Install
- kein Live-Test

## Coordination posture
- **Protected functional pairing ref for HA/releaser coordination:** `8b017a74`
- **Current larger functional milestone above the protected pairing ref:** `3e135e21`
- **Exact current docs/release-prep head:** use the current repo HEAD validated by `./scripts/check_15_2_0_release_gate.sh`; for real handoff/cut discussion, treat the refreshed workspace release entrypoint as the exact current-head snapshot surface.
- **Rule:** Release-readiness / reviewer / releaser docs dürfen oberhalb des geschützten Pairing-Refs weiterlaufen, solange der Pairing-Ref explizit stabil bleibt.

## Milestone slices committed above the protected pairing ref
- `e683afe0` — `feat(core): drive zone health from truth-lane zones`
- `4deab194` — `fix(core): harden calendar and homekit api deps`
- `b04f7d73` — `feat(core): drive zone aggregates from truth-lane zones`
- `7e4d7e62` — `fix(core): degrade zone aggregate scene endpoints without requests`
- `9024e745` — `fix(core): degrade scene write paths without requests`
- `3e135e21` — `feat(core): harden optional blueprints and proposal handoffs`

## Validation snapshot on current packaging head
Commands:
```bash
./scripts/check_15_2_0_releaser_pointers.sh
./scripts/check_15_2_0_sync_anchor_consistency.sh
./scripts/run_core_contract_bundle.sh
pytest -q tests/test_zone_aggregates_blueprint_contract.py tests/test_zone_aggregates_truth_contract.py tests/test_scenes_blueprint_contract.py tests/test_optional_blueprint_wiring_contract.py tests/test_habitus_accept_contract.py
```

Result:
- **64 tests passed** in the contract bundle
- **13 targeted tests passed** for the latest aggregates/scenes/optional-blueprint hardening lanes
- **0 warnings**

## Draft GitHub release bullets
### Headline
- Core truth-lane + optional-dependency hardening expanded while keeping the protected HA/releaser pairing ref stable.

### Added
- Zone Health now reads truth-lane zones from `hub_zones` and merges role assignments from `zone_automation`.
- Zone Aggregates now also reads truth-lane zones first and exposes `zone_type`, `enabled_modules`, and `entities_by_role` in the API response.
- New contract suites:
  - `tests/test_zone_health_truth_contract.py`
  - `tests/test_zone_aggregates_truth_contract.py`
  - `tests/test_zone_aggregates_blueprint_contract.py`
  - `tests/test_scenes_blueprint_contract.py`
  - `tests/test_calendar_blueprint_contract.py`
  - `tests/test_homekit_blueprint_contract.py`
  - `tests/test_api_v1_syntax_contract.py`
  - `tests/test_optional_blueprint_wiring_contract.py`
  - `tests/test_flat_blueprint_registry_contract.py`
  - `tests/test_flat_blueprint_registry_attr_contract.py`
  - `tests/test_habitus_accept_contract.py`
  - `tests/test_anomaly_blueprint_contract.py`
  - `tests/test_conversation_blueprint_contract.py`
  - `tests/test_entity_assignment_blueprint_contract.py`
  - `tests/test_mcp_blueprint_contract.py`
  - `tests/test_onyx_bridge_blueprint_contract.py`
  - `tests/test_styx_voice_blueprint_contract.py`
  - `tests/test_weather_blueprint_contract.py`

### Changed
- Calendar endpoints now degrade cleanly with `503` when optional HTTP dependencies are absent.
- HomeKit status/toggle stays usable without `requests`; only HA reload is skipped.
- Zone Aggregate scene capture/apply degrades cleanly without `requests`, while read-only aggregate views remain available.
- Scene create/apply degrades cleanly without `requests`, while scene listing/presets/context remain readable.
- Additional optional blueprints (`anomaly`, `conversation`, `entity_assignment`, `mcp`, `onyx_bridge`, `styx_voice`, `weather`) now fail closed/structured instead of disappearing silently.
- `habitus` proposal acceptance now emits a normalized `ha_output` envelope via `habitat_adapter`.
- `transaction_log` falls back to UUID4 when `ulid` is unavailable.

### Release-readiness packaging
- Repo-local release pointer / manifest / workspace entrypoint stay available as the single release-prep entry surface.
- Queue / governance / real-release runbook surfaces are available repo-locally for reviewer/releaser flow.
- Protected pairing ref remains explicit: `8b017a74`.
- The strict release gate treats the workspace release entrypoint as the exact current-head snapshot surface for real cut discussion.

## Exact reviewer/releaser note
- For HA/releaser pairing and protected cutover discussion, continue to treat **`8b017a74`** as the functional pairing ref until a newer functional cutover ref is explicitly validated and coordinated.
- For GitHub release packaging / docs / notes / manifest generation, use the current repo head validated by `./scripts/check_15_2_0_release_gate.sh` and exported via the refreshed workspace release entrypoint / release surfaces.
