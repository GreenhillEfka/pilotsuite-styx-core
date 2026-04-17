# Changelog

## [Unreleased]

### Changed
- Removed the stale top-level HA integration README from `copilot_core/`; canonical HA/HACS install docs remain in `pilotsuite-styx-ha`
- Realigned the root `VERSION` file to `20.0.8`, so release/install surfaces now match `addons/pilotsuite/app/VERSION` and `addons/pilotsuite/config.yaml`

## [20.0.2] - 2026-04-08

### Fixed
- Core add-on Docker build context now uses the canonical add-on path under `addons/pilotsuite/`
- Removed release ambiguity around legacy `pilotsuite_core/rootfs/...` copy paths
- Prepared a fresh clean release asset for Home Assistant add-on installation

## [20.0.0] - 2026-04-08

### Changed
- **BREAKING:** Add-on structure reorganized to `addons/pilotsuite/`
- Version synchronized with HA Integration (v20.0.0)
- Backend source remains in `pilotsuite_core/`

### Added
- Complete Add-on structure for Home Assistant
- config.yaml, Dockerfile, run.sh
- repository.yaml for Add-on Store discovery

### Fixed
- Add-on directory structure for Supervisor compatibility
- Version consistency across all config files

### Migration Notes

**Upgrading from previous versions:**
1. Backup your configuration
2. Uninstall old add-on version
3. Install v20.0.0 from Add-on Store
4. Restore configuration
5. Restart Home Assistant

---

## [1.0.0] - 2026-04-07

### Added
- Initial Platinum release
- Complete API v1
- Brain Graph implementation
- Neural sensor suite
