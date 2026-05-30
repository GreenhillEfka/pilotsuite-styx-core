# PilotSuite Core API Reference

## Canonical source paths

- Runtime app: `addons/pilotsuite/app/`
- API modules: `addons/pilotsuite/app/copilot_core/api/v1/`
- OpenAPI-style integration spec: `docs/integrations/onyx_styx_actions.openapi.yaml`

## Public verification endpoints

- `GET /health`
- `GET /version`

## Main API family prefix

- `/api/v1/`

Representative families include:
- zones
- presence
- analytics
- notifications
- voice
- styx surfaces

For route-level implementation truth, inspect `addons/pilotsuite/app/copilot_core/api/v1/`.
