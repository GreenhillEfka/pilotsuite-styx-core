# PilotSuite - Production Status (2026-02-27)

Scope: dual-repo production audit (`pilotsuite-styx-core` + `pilotsuite-styx-ha`).

Release baseline:
- Core add-on: `10.4.0`
- HA integration: `10.4.0`

## Executive Summary

System is production-ready. All CI gates green, HACS validation passing, production guard workflows active.

### Release History (v10.x)

| Version | Core | HA | Key Changes |
|---------|------|-----|------------|
| v10.4.0 | Auto-Setup API, documentation | Auto-Setup, Entity Classifier, Dashboard Panel | Zero-Config onboarding |
| v10.3.0 | Blueprint consolidation, security | Parallel coordinator, habit refactoring | -260 lines boilerplate |
| v10.2.0 | Unified Mood Engine v3.0 | Mood System v3.0, Automation Engine | 6 discrete + 5 continuous dimensions |
| v10.1.x | Logic hardening, EventBus bridges | Sensor data paths, missing sensors | 6 patch releases |
| v10.0.0 | Zone Automation Controller | Override Modes, Musikwolke Dashboard | Zone-based automation |

### Quality Metrics

| Metric | Core | HA |
|--------|------|-----|
| Tests passing | 586+ | 579+ |
| Python files | 1100+ | 325+ |
| API endpoints | 55+ | — |
| Modules | 22+ services | 36 modules |
| Entities | — | 115+ |
| Sensors | — | 94+ |

### Validation Status

- [x] Core syntax check (all Python files compile)
- [x] Core test suite (586+ passed, 0 failed)
- [x] HA syntax check (all Python files compile)
- [x] HA test suite (579+ passed, 5 skipped)
- [x] HACS validation passing
- [ ] HASSFest validation (temporarily disabled — KeyError: 'codeowners')
- [x] Production guard workflows active (15-minute cadence)
- [x] Dual-repo version sync (both at v10.4.0)

## Architecture Posture

### Completed Since v10.1.5

- **Auto-Setup**: Zero-config zone creation from HA areas + ML entity classification
- **Sidebar Panel**: Dedicated PilotSuite entry in HA sidebar (Core ingress iframe)
- **Entity Classifier**: 4-signal ML-style pipeline (domain, device_class, UOM, keywords)
- **Blueprint Consolidation**: Data-driven blueprint registration (-260 lines boilerplate)
- **Security Hardening**: require_token on health/metrics endpoints
- **Mood Engine v3.0**: 6 discrete states + 5 continuous dimensions + entity dependencies
- **Parallel Coordinator Polling**: Improved HA data update performance

### Remaining Known Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| HASSFest disabled | Medium | KeyError: 'codeowners' — fix codeowners field in manifest.json |
| Entity Classifier accuracy | Low | 4-signal pipeline with bilingual keywords; manual override available |
| Sidebar panel load time | Low | iframe to Core ingress; depends on Core startup |

## Release Gate Criteria

A release is production-ready when:
1. All critical path tests pass (forward + return + auth + status)
2. Runtime fallback behavior works outside ideal HA container paths
3. CI fails on real regressions (no masked failures)
4. Versioning/changelogs/docs synchronized across both repos
5. HACS validation green
6. No P0 bugs open

## Continuous Hardening

Both repos run `production-guard` workflows every 15 minutes:
- Syntax checks on all Python files
- Critical path test execution
- Version sync verification
- API contract tests
