# H2 Blueprint / OpenAPI / Runtime Reconciliation

## Summary
- Total config entries checked: **101**
- Import/attr OK: **101**
- Drift entries: **0**
- Status breakdown: `{'ok': 101}`
- Error breakdown: `{}`

## Top Priority Drift Cases

## Recommended Fix Order
- 1. Fix SyntaxError/NameError modules first because they break registration deterministically.
- 2. Fix ModuleNotFoundError/ImportError next by restoring bridge paths or correcting module references.
- 3. Fix AttributeError mismatches by aligning blueprint attr names in blueprints_config to real exports.
- 4. Re-run core wiring tests after each batch, then regenerate this report.

## Check Commands
- `python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py`
- `python3 -m pytest -q tests/test_h1_truth_map.py tests/test_api_v1_syntax_contract.py tests/test_core_wiring_contract.py`
- `python3 scripts/h2_blueprint_reconcile.py --repo . --md-out docs/analysis/H2_BLUEPRINT_RECONCILIATION.md --json-out docs/analysis/h2_blueprint_reconciliation.json`

