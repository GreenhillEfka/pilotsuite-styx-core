# PilotSuite Core Index

Quick orientation for the Core add-on repository (`pilotsuite-styx-core`).

## Current Baseline

- Version: `8.9.0`
- Runtime: Flask + Waitress on port `8909`
- LLM mode: local-first (`qwen3:0.6b`) with optional cloud fallback (`https://ollama.com/v1`, default cloud model `qwen3.5:cloud`)
- Companion integration: `pilotsuite-styx-ha`

## Main Paths

- Add-on metadata: `copilot_core/config.yaml`, `copilot_core/manifest.json`
- App runtime: `copilot_core/rootfs/usr/src/app/`
- Core services/APIs: `copilot_core/rootfs/usr/src/app/copilot_core/`
- Ingress dashboard template: `copilot_core/rootfs/usr/src/app/templates/dashboard.html`
- Startup scripts: `copilot_core/rootfs/usr/src/app/start_dual.sh`
- Tests: `copilot_core/rootfs/usr/src/app/tests/`

## Key API Surfaces

- System: `/health`, `/version`, `/api/v1/status`
- Chat: `/v1/chat/completions`, `/v1/models`, `/chat/status`
- Habitus: `/api/v1/habitus/*`, `/api/v1/hub/habitus/*`
- Module control: `/api/v1/modules/*`
- Media zones: `/api/v1/media/*`
- RAG: `/api/v1/rag/*`
- Onyx bridge: `/api/v1/onyx/*`

## Product Direction (React-first)

- React ingress dashboard is the primary operations UI.
- Legacy YAML dashboards are optional compatibility mode.
- Module config, model routing (primary/secondary), Habitus management, and media workflows are maintained in API + React UI together.

## Release/Docs

- Release notes: `RELEASE_NOTES.md`
- Changelog: `CHANGELOG.md` and `copilot_core/CHANGELOG.md`
- Vision: `VISION.md`
- Roadmap: `docs/ROADMAP.md`
- Onyx integration: `docs/ONYX_INTEGRATION.md`
