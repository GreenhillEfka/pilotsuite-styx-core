#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/export_workspace_core_handoff.sh >/dev/null
./scripts/export_15_2_0_release_manifest.sh >/dev/null

printf 'Refreshed release surfaces:\n'
printf ' - %s\n' "$ROOT/docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_entrypoint.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_target.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_pairing.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_harness_evidence.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_rc_input_chain.json"
