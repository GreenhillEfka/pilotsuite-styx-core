# Slice 179: HACS Gating Mechanism

**Status:** Analyzed (2026-04-06)
**Basis:** HACS integration requirements

## Target
Implement a safety gate for HACS installs to prevent unstable version propagation.

## Mechanism
1. **Lock-Check:** Core checks if a release-lock is active.
2. **Health-Gate:** Only allow HACS pull if last 30 min of system health was "green".
3. **Version-Parity:** Ensure manifest.json in Core matches the integration state.

## Decision
Add `/api/v1/hacs/gate` endpoint for Home Assistant to query before showing update notification.

