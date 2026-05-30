# PilotSuite Core — Home Assistant Add-on

**Version:** 20.0.10  
**License:** MIT  
**Author:** GreenhillEfka

PilotSuite Core is the canonical Home Assistant add-on that runs the PilotSuite backend, API surface, and operator UI.

## Install order

1. Install **PilotSuite Core** from this repository.
2. Install **PilotSuite HA** from `https://github.com/GreenhillEfka/pilotsuite-styx-ha`.

## Canonical repo layout

- `README.md` , public entrypoint for this repository
- `addons/pilotsuite/` , canonical add-on packaging tree
- `addons/pilotsuite/app/` , canonical runtime application tree
- `addons/pilotsuite/app/copilot_core/` , canonical Python package and API source
- `copilot_core/` , legacy archive surface only, not release truth

## Installation

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for the full path.

Quick path:
1. Add `https://github.com/GreenhillEfka/pilotsuite-styx-core` to the Home Assistant add-on store.
2. Install **PilotSuite Core**.
3. Configure `log_level`, `ollama_host`, and `ollama_port`.
4. Start the add-on.
5. Open the add-on UI or connect to `http://<home-assistant-host>:8909`.

## First verification path

1. Confirm the add-on is running.
2. Check `GET /health` and `GET /version` on port `8909`.
3. Open the add-on UI and confirm the runtime responds without path guessing.

## Smoke test path

- Runtime smoke: `GET /health`, `GET /version`
- Repo smoke: see [docs/TESTING.md](docs/TESTING.md)

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Testing](docs/TESTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [API Reference](docs/API_REFERENCE.md)

## Support

- Issues: https://github.com/GreenhillEfka/pilotsuite-styx-core/issues
- HA integration repo: https://github.com/GreenhillEfka/pilotsuite-styx-ha
- Changelog: [CHANGELOG.md](CHANGELOG.md)
