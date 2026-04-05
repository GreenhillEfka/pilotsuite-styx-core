# Slice 180: HACS Discovery Wiring

**Status:** Analyzed (2026-04-06 00:12)
**Basis:** HACS custom repository integration

## Target
Enable Home Assistant to discover PilotSuite Core as a HACS-installable integration.

## Mechanism
1. **repository.json** — HACS manifest for discovery
2. **Endpoint Exposure** — `/api/hacs/discovery` for HA polling
3. **Version Sync** — Ensure HACS sees same version as Core manifest

## Decision
Create HACS discovery endpoint + repository metadata.

