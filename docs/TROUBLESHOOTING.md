# PilotSuite Core Troubleshooting

## The add-on will not start

- Re-check the add-on configuration values.
- Confirm Home Assistant can start add-ons normally.
- Review add-on logs before changing paths or legacy files.

## `/health` or `/version` does not respond

- Confirm the add-on is running.
- Confirm you are using port `8909`.
- Re-check host networking or ingress access from Home Assistant.

## Version values do not match

Canonical version truth for this repo must stay aligned across:
- `README.md`
- `VERSION`
- `addons/pilotsuite/config.yaml`
- `addons/pilotsuite/app/VERSION`

## Legacy path confusion

If you find references to top-level `copilot_core/` release paths, treat them as legacy archive material. Current release truth lives under `addons/pilotsuite/`.
