# Release Notes - PilotSuite Core

## [8.1.1] - 2026-02-25 — VERSION SYNC

### Added
- None

### Changed
- Version sync: `config.yaml` and `VERSION` file aligned to `8.1.1`
- Minor version bump to reflect runtime/file consistency

### Fixed
- `config.yaml` version drift (was 7.40.0, now 8.1.1)

### Testing
- Version resolution validated
- Runtime version returns `8.1.1` consistently

## [8.1.0] - 2026-02-25 — MCP PHASE 2: WEB SEARCH + TEST SUITE

### Added
- **MCP Phase 2: Web Search via SearXNG**
  - New MCP tool: `pilotsuite.search_web`
  - Supports query, language, categories, time_range, safesearch, max_results
  - Integration with local SearXNG instance (http://192.168.30.18:4041)
- **Enhanced MCP Test Suite**
  - `test_mcp_web_search_tool_exists` – verifies search_web tool registration
  - `test_mcp_web_search_tool_schema` – validates input schema

### Changed
- MCP_TOOLS extended with web search capability
- VERSION bumped to 8.1.0
- All MCP tools now return structured JSON results

### Fixed
- None

### Testing
- pytest passed: MCP server contract tests
- SearXNG endpoint reachable
- Web search tool schema validated

---

## [7.26.0] - 2026-02-25 — INPUT NUMBER + ZONES + PATTERN APIs

### Added
- `input_number` API: `/api/v1/input_number` GET/POST
- `zones` API: `/api/v1/zones` GET
- `scene_patterns` API: `/api/v1/scenes/patterns` (record, suggest, summary, clear)
- `routine_patterns` API: `/api/v1/routines` (record, predict, typical, summary, clear)
- `push_notifications` API: `/api/v1/notifications` (send, channels, test)

### Changed
- Manifest v7.26.0
- All new APIs registered in blueprint.py

### Fixed
- Push notifications: fixed syntax error in validation

### Testing
- All API files syntax OK (py_compile)
- Blueprint registration validated

### Release Checklist
- [x] CHANGELOG.md aktualisiert
- [x] Version in `copilot_core/config.yaml` bumped
- [x] Commit mit `release: v7.26.0` prefix
- [x] Tag erstellt `v7.26.0`
- [x] Branch gepusht

---

## [7.8.9] - 2026-02-23 — ERROR ISOLATION + CONNECTION POOLING

### Added
- Module-Crash-Isolation über `ModuleErrorBoundary`
- Connection Pooling für HA-ClientSessions
- Error Dashboard Widget zur Visualisierung

### Changed
- Error handling in `__init__.py` überarbeitet
- Session-Management in `api/__init__.py`

### Fixed
- Haushalts-Error-Kaskaden verhindert
- Resource-Leaks bei HA-Updates

### Testing
- pytest passed: 520 tests
- hassfest: ✅ OK
- local Ollama: ✅ OK
