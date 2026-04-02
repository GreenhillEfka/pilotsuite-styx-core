# H2 Blueprint / OpenAPI / Runtime Reconciliation

## Summary
- Total config entries checked: **101**
- Import/attr OK: **89**
- Drift entries: **12**
- Status breakdown: `{'import_failed': 9, 'ok': 89, 'attribute_missing': 3}`
- Error breakdown: `{'ModuleNotFoundError': 8, 'ImportError': 1, 'AttributeError': 3}`

## Top Priority Drift Cases
- **ModuleNotFoundError** `copilot_core.api.v1.config` :: expected `config_bp` — No module named 'copilot_core.api.v1.config'
- **ModuleNotFoundError** `copilot_core.api.v1.entity_normalization` :: expected `entity_normalization_bp` — No module named 'copilot_core.api.v1.entity_normalization'
- **ModuleNotFoundError** `copilot_core.api.v1.health` :: expected `health_bp` — No module named 'copilot_core.api.v1.health'
- **ModuleNotFoundError** `copilot_core.api.v1.openai_compat` :: expected `openai_compat_bp` — No module named 'copilot_core.api.v1.openai_compat'
- **ModuleNotFoundError** `copilot_core.api.v1.openai_compat` :: expected `openai_compat_bp` — No module named 'copilot_core.api.v1.openai_compat'
- **ImportError** `copilot_core.api.v1.rag` :: expected `rag_bp` — cannot import name 'NamespaceIndex' from 'copilot_core.rag.indexer' (/config/clawd/team/worktrees/pilotsuite-styx-core-current/copilot_core/rootfs/usr/src/app/copilot_core/rag/indexer.py)
- **ModuleNotFoundError** `copilot_core.api.v1.user_management` :: expected `user_management_bp` — No module named 'copilot_core.api.v1.user_management'
- **ModuleNotFoundError** `copilot_core.api.v1.users` :: expected `users_bp` — No module named 'copilot_core.api.v1.users'
- **ModuleNotFoundError** `copilot_core.api.v1.version` :: expected `version_bp` — No module named 'copilot_core.api.v1.version'
- **AttributeError** `copilot_core.api.v1.mcp` :: expected `mcp_bp` — copilot_core.api.v1.mcp has no attribute mcp_bp
- **AttributeError** `copilot_core.api.v1.user_hints` :: expected `user_hints_bp` — copilot_core.api.v1.user_hints has no attribute user_hints_bp
- **AttributeError** `copilot_core.api.v1.zones` :: expected `zones_bp` — copilot_core.api.v1.zones has no attribute zones_bp

## Recommended Fix Order
- 1. Fix SyntaxError/NameError modules first because they break registration deterministically.
- 2. Fix ModuleNotFoundError/ImportError next by restoring bridge paths or correcting module references.
- 3. Fix AttributeError mismatches by aligning blueprint attr names in blueprints_config to real exports.
- 4. Re-run core wiring tests after each batch, then regenerate this report.

## Check Commands
- `python3 -m py_compile copilot_core/rootfs/usr/src/app/copilot_core/core_setup.py`
- `python3 -m pytest -q tests/test_h1_truth_map.py tests/test_api_v1_syntax_contract.py tests/test_core_wiring_contract.py`
- `python3 scripts/h2_blueprint_reconcile.py --repo . --md-out docs/analysis/H2_BLUEPRINT_RECONCILIATION.md --json-out docs/analysis/h2_blueprint_reconciliation.json`

