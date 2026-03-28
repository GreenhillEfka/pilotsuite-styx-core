#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MANIFEST_PATH="docs/CORE_15_2_0_RELEASE_MANIFEST_2026-03-27.json"
WORKSPACE_ENTRYPOINT="/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_entrypoint.json"

./scripts/export_workspace_core_handoff.sh >/dev/null
./scripts/export_15_2_0_release_manifest.sh >/dev/null

# Keep the repo worktree clean while preserving the exact current-head snapshot
# in the workspace export surfaces used for real handoff/cut discussion.
git checkout -- "$MANIFEST_PATH"

printf 'Refreshed release surfaces (workspace-exact snapshot preserved, repo manifest restored):\n'
printf ' - %s\n' "$WORKSPACE_ENTRYPOINT"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_target.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_release_pairing.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_workspace_harness_evidence.json"
printf ' - %s\n' "/config/clawd/team/workspaces/pilotsuite-stxy-sandbox/handoff/core_rc_input_chain.json"
printf 'Repo manifest restored to committed state: %s\n' "$ROOT/$MANIFEST_PATH"
