# Repository Guidelines

## Project Structure & Module Organization
This repository contains the PilotSuite Styx Core add-on and API backend.

- Add-on metadata: `copilot_core/config.yaml`, `copilot_core/build.yaml`
- Runtime app: `copilot_core/rootfs/usr/src/app/`
- API and services: `copilot_core/rootfs/usr/src/app/copilot_core/`
- Dashboard template/static: `copilot_core/rootfs/usr/src/app/templates/`, `.../static/`
- Startup scripts: `copilot_core/rootfs/usr/src/app/start_dual.sh`
- Tests: `copilot_core/rootfs/usr/src/app/tests/`

This repo is tightly coupled with `pilotsuite-styx-ha`; endpoint, payload, and auth changes must stay integration-compatible.

## Build, Test, and Development Commands
- Run targeted Core tests (recommended local loop):  
  `cd /Users/andreas/pilotsuite-styx-core/copilot_core/rootfs/usr/src/app && pytest -q tests/test_api_endpoints.py`
- Dashboard/API regression tests:  
  `pytest -q tests/test_dashboard_endpoints.py tests/test_llm_provider_fallback.py`
- Single test file:  
  `pytest -q tests/test_dashboard_template_habitus.py`

Prefer targeted suites first; run broader suites before release/tag creation.

## Coding Style & Naming Conventions
- Python and Jinja/JS frontend; keep changes minimal and explicit.
- Python style: 4-space indentation, type hints where practical.
- Naming: `snake_case` functions/vars, `PascalCase` classes, `UPPER_CASE` constants.
- Keep endpoint paths stable; when migrating, provide compatibility fallbacks.
- Do not silently break auth-protected dashboard flows.

## Testing Guidelines
- Framework: `pytest`.
- Test files must follow `test_*.py`.
- Add regression tests for:
  - API route/path changes
  - dashboard frontend API usage
  - LLM/provider fallback behavior
- Ensure new behavior is covered before tagging releases.

## Commit & Pull Request Guidelines
- Commit style: imperative, scope-first.  
  Example: `fix dashboard habitus zone flow and room selector`
- Include version/changelog updates in release commits.
- PR/release notes should include impact, files changed, and passing test evidence.

## Security & Configuration Tips
- Never commit real auth tokens or cloud API keys.
- Preserve support for both `Bearer` and `X-Auth-Token`.
- Validate startup behavior with/without Ollama and with cloud fallback configured/unconfigured.
