# Changelog

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

