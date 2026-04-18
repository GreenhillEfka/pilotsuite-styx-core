# CORE-STRUCT-101 — Runtime/API Hardening Analysis

**Stand:** 2026-04-18 10:00 Europe/Berlin  
**Task:** CORE-STRUCT-101 Runtime/API härten  
**Verification:** compile ring + full test suite

---

## File Radius Verified

### `copilot_core/__init__.py` (repo-root)
- **Addon path extension:** `_ADDON_APP_PACKAGE` extends `__path__` to include addon surface
- **`__version__`:** forwarded from addon path via try/except fallback chain
- **`__all__`:** added — 13 explicit public API names
  - Version: `__version__`
  - HA entry points: `DOMAIN`, `PLATFORMS`, `CONFIG_SCHEMA`, `async_setup`, `async_setup_entry`, `async_unload_entry`, `async_remove_entry`
  - HA guard: `HAS_HOMEASSISTANT`, `_require_homeassistant_runtime`
  - Service schemas: `SERVICES`
  - Build helpers: `_build_notification_config`, `_build_calendar_config`
- **Standalone-safe:** `_require_homeassistant_runtime()` fails with clear message when imported without HA

### `addons/pilotsuite/app/copilot_core/core_setup.py`
- **Public init API:** `init_services(hass, config)` — async, returns `services` dict
- **Public blueprint API:** `register_blueprints(app, services)` — flat registration, isolated failures
- **Startup tracking:** `services["startup_time_ms"]` — millisecond-precision init timing
- **Blueprint data-driven:** `_BLUEPRINTS` list — single import failure doesn't cascade
- **lazy_load:** Configurable heavy-module deferral

### `addons/.../api/v1/module_health.py`
- **Ready surface:** `module_health_bp` — GET `/api/v1/modules/health/dashboard`
- **Wired by:** `init_module_health_api(module_registry, integration_bus, hebbian_learning, cross_module_analyzer, feedback_loop)`
- **Endpoints:** `/dashboard`, `/learning`, `/patterns`

### `addons/.../monitoring/health.py`
- **`HealthChecker` class:** Full async health check (CPU, memory, disk, Python deps, external services, storage)

---

## Key Findings

1. **No `runtime_health.py` file exists** at `copilot_core/health/` — this was the reference in earlier planning docs. Current truth uses `module_health.py` + `monitoring/health.py` as the two health surfaces.
2. **`__all__` was missing** from repo-root `__init__.py` — added, 13 items
3. **Addon path extension** is correctly placed before the version import try block ✅
4. **Startup timing** is tracked (`startup_time_ms`) but not exposed via a public API — within scope for future

---

## Compile Verification

```bash
python3 -m py_compile \
  copilot_core/__init__.py \
  addons/pilotsuite/app/copilot_core/core_setup.py \
  addons/pilotsuite/app/copilot_core/api/v1/module_health.py \
  addons/pilotsuite/app/copilot_core/monitoring/health.py
# ✅ ALL OK
```

## Test Verification

```bash
python -m pytest tests/ -q
# 468 passed, 3 skipped
```

---

## Scope Note for CORE-STRUCT-101

This task is **verification and minor hardening only** — the runtime/API surface was already structurally sound. No architectural changes were required.

**Next:** CORE-STRUCT-103 State/Persistenz → CORE-STRUCT-102 Voice/Memory (per execution order in CORE-STRUCT-104)
