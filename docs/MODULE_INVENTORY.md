# PilotSuite Module Inventory (2026-02-22)

This inventory reflects the production-ready dual-repo baseline at `v7.7.13`.

## Scope
- Core add-on backend: `pilotsuite-styx-core`
- HA integration frontend/runtime: `pilotsuite-styx-ha`

## Runtime module counts
- HA runtime modules loaded by default: `31`
- HA sensor implementation files: `54` (multiple entities per file)
- Core package domains under `copilot_core/`: `30`

## Core subsystem inventory
- Event ingest and store: receives N3 envelopes and applies idempotency.
- Brain graph: node/edge model, pruning, neighborhood and state APIs.
- Habitus mining: pattern discovery and candidate creation.
- Candidate store: lifecycle states (`pending/offered/accepted/dismissed/deferred`).
- Mood + neurons: contextual scoring and recommendation weighting.
- Knowledge/vector/memory: semantic retrieval and long-context support.
- Conversation layer: OpenAI-compatible endpoints plus local model runtime.
- Hub engines: domain-specific advanced orchestration APIs.

## HA runtime module inventory (loaded set)
- `legacy`
- `performance_scaling`
- `events_forwarder`
- `history_backfill`
- `dev_surface`
- `habitus_miner`
- `ops_runbook`
- `unifi_module`
- `brain_graph_sync`
- `candidate_poller`
- `media_zones`
- `mood`
- `mood_context`
- `energy_context`
- `network`
- `weather_context`
- `knowledge_graph_sync`
- `ml_context`
- `camera_context`
- `quick_search`
- `voice_context`
- `home_alerts`
- `character_module`
- `waste_reminder`
- `birthday_reminder`
- `entity_tags`
- `person_tracking`
- `frigate_bridge`
- `scene_module`
- `homekit_bridge`
- `calendar_module`

## Communication pipeline map
Forward path:
- HA state/service events -> N3 forwarder -> `POST /api/v1/events` -> Core processor/graph/miner.

Return path:
- `GET /api/v1/candidates` -> Candidate poller -> Repairs workflow -> user decision -> `PUT /api/v1/candidates/:id`.

Realtime path:
- Core webhook -> HA coordinator merge -> entities/cards refresh.

## Test-backed verification
Core critical tests:
- `test_app_smoke.py`
- `test_status_endpoint.py`
- `test_auth_security.py`
- `test_events_endpoint.py`
- `test_full_flow.py`
- `test_e2e_pipeline.py`

HA critical tests:
- `tests/integration/test_full_flow.py`
- `tests/test_forwarder_n3.py`
- `tests/test_candidate_poller_integration.py`
- `tests/test_repairs_workflow.py`
- `tests/test_core_api_v1_v2.py`

## Continuous guardrail
A scheduled production guard workflow runs every 15 minutes in both repos to continuously verify these critical paths.
