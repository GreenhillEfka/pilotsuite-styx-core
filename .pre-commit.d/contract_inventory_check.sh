#!/bin/bash
# Pre-commit gate: Contract Inventory Auto-Check (Hybrid Mode)
# - Leicht-Check bei normalen Commits (Runtime-Module nur)
# - Voll-Check bei Slice-Grenzen/CI (mit OpenAPI)
#
# Usage:
#   ./contract_inventory_check.sh              # Leicht (default)
#   ./contract_inventory_check.sh --full       # Voll (Slice/CI)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

FULL_CHECK=false
if [[ "$1" == "--full" ]] || [[ "$CI" == "true" ]] || [[ "$SLICE_BOUNDARY" == "true" ]]; then
    FULL_CHECK=true
fi

echo "Running Contract Inventory Auto-Check ($( [[ $FULL_CHECK == true ]] && echo 'FULL' || echo 'LIGHT' ))..."

cd "$REPO_ROOT"

if [[ $FULL_CHECK == true ]]; then
    /home/linuxbrew/.linuxbrew/bin/python3 scripts/contract_inventory_check.py --repo .
else
    # Light mode: Runtime modules only (skip OpenAPI comparison)
    /home/linuxbrew/.linuxbrew/bin/python3 scripts/contract_inventory_check.py --repo . --light
fi

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Contract inventory consistent"
else
    echo "❌ Contract drift detected — commit blocked"
    echo ""
    echo "Fix drift before committing:"
    echo "  1. Restore missing modules, or"
    echo "  2. Update blueprints_config.py, or"
    echo "  3. Regenerate OpenAPI spec"
fi

exit $EXIT_CODE
