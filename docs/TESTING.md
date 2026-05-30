# PilotSuite Core Testing

## Fresh-operator smoke path

1. Start the add-on.
2. Verify `GET /health` returns success.
3. Verify `GET /version` reports `20.0.8`.
4. Confirm the add-on UI opens without path fixes.

## Maintainer smoke path

Run from the repository root:

```bash
python -m py_compile addons/pilotsuite/app/main.py addons/pilotsuite/app/copilot_core/app.py
PYTHONPATH=addons/pilotsuite/app python -m pytest addons/pilotsuite/app/copilot_core/tests -q
```

## Canonical test paths

- Runtime code: `addons/pilotsuite/app/`
- Tests: `addons/pilotsuite/app/copilot_core/tests/`
- Workflow checks: `.github/workflows/ci.yml`
