# CHANGELOG

## v7.10.2 (2026-02-24)
- Version bump to v7.10.2 — sync with main branch merge
- Fixed pyproject package name to `ai_home_copilot_client`
- Resolved import errors in SDK tests
- Synchronized core and HA versions

## v7.10.1 (2026-02-24)
- Auto-release: System integrity checks and minor fixes
- Updated version in config and manifest

## v7.10.0 (2026-02-24)
- Plugin system v1 — base classes, search/llm plugins, React backend API
- Search plugin via SearXNG (local, HTML parser)
- LLM plugin — Ollama/Cloud integration
- Web UI toggle API (`/api/plugins/*`)
- HA manifest.json extended with `searxng_enabled`, `searxng_base_url`

## v7.9.2 (2026-02-24)
- Bugfix: connection pooling in llm_provider
- Feature: SearXNG integration for web search

## v7.9.1 (2026-02-24)
- Added SearXNG search plugin (plugins/search/) for local web search
- Added HA-conform manifest.json with optional searxng config
- Cleaned up dev branches — all releases now go directly to main
- HA hassfest compliant structure

## v7.8.13 (2026-02-24)
- Cross-Home Sharing + Autopilot Runner v0.1.0

## v7.8.12 (2026-02-24)
- Phase 5: NotificationSensor + SceneIntelligenceSensor
- 31 API endpoints registered

## v7.8.11 (2026-02-23)
- Fixed error isolation and connection pooling
- Added unit tests for error boundary and status tracking
