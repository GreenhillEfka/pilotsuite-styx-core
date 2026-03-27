#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

EXPECTED_CORE_SOURCE="/config/clawd/team/repos/pilotsuite-styx-core"
EXPECTED_PAIRED_CORE_REF="8b017a74"
EXPECTED_VERSION="15.2.0"
CURRENT_HEAD="$(git rev-parse --short=8 HEAD)"

DOCS=(
  "docs/CORE_15_2_0_BUILDER_HANDOFF_2026-03-27.md"
  "docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md"
  "docs/CORE_BUILDER_HANDOFF_2026-03-27.md"
  "docs/CORE_RC_PREP_2026-03-27.md"
  "docs/CORE_RELEASE_INPUT_2026-03-27.md"
  "docs/CORE_REVIEW_PACKET_2026-03-27.md"
  "docs/HA_RELEASE_CONTRACT_HANDOFF_2026-03-27.md"
)

PAIRED_REF_DOCS=(
  "docs/CORE_15_2_0_BUILDER_HANDOFF_2026-03-27.md"
  "docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md"
  "docs/CORE_BUILDER_HANDOFF_2026-03-27.md"
  "docs/CORE_RC_PREP_2026-03-27.md"
  "docs/CORE_RELEASE_INPUT_2026-03-27.md"
  "docs/CORE_REVIEW_PACKET_2026-03-27.md"
)

failures=0

printf 'Core 15.2.0 sync-anchor consistency check\n'
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Current HEAD: %s\n' "$CURRENT_HEAD"
printf 'Expected paired Core ref: %s\n' "$EXPECTED_PAIRED_CORE_REF"

actual_version="$(tr -d '[:space:]' < VERSION)"
if [[ "$actual_version" == "$EXPECTED_VERSION" ]]; then
  printf 'PASS version=%s\n' "$actual_version"
else
  printf 'FAIL expected version %s, got %s\n' "$EXPECTED_VERSION" "$actual_version"
  failures=$((failures + 1))
fi

for doc in "${DOCS[@]}"; do
  if [[ ! -f "$doc" ]]; then
    printf 'FAIL missing %s\n' "$doc"
    failures=$((failures + 1))
    continue
  fi

  if grep -Fq "$EXPECTED_CORE_SOURCE" "$doc"; then
    printf 'PASS %s authoritative source\n' "$doc"
  else
    printf 'FAIL %s missing authoritative source\n' "$doc"
    failures=$((failures + 1))
  fi
done

for doc in "${PAIRED_REF_DOCS[@]}"; do
  if grep -Fq "$EXPECTED_PAIRED_CORE_REF" "$doc"; then
    printf 'PASS %s paired-ref=%s\n' "$doc" "$EXPECTED_PAIRED_CORE_REF"
  else
    printf 'FAIL %s missing paired-ref %s\n' "$doc" "$EXPECTED_PAIRED_CORE_REF"
    failures=$((failures + 1))
  fi
done

SYNC_DOC="docs/CORE_15_2_0_SYNC_ANCHOR_2026-03-27.md"
if grep -Fq "$CURRENT_HEAD" "$SYNC_DOC"; then
  printf 'NOTE %s mentions current-head=%s\n' "$SYNC_DOC" "$CURRENT_HEAD"
else
  printf 'NOTE %s does not pin current-head=%s (expected for docs/readiness commits above the paired ref)\n' "$SYNC_DOC" "$CURRENT_HEAD"
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
