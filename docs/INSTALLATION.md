# PilotSuite Core Installation

## Canonical install path

Install order:
1. PilotSuite Core add-on from this repository
2. PilotSuite HA integration from `https://github.com/GreenhillEfka/pilotsuite-styx-ha`

## Home Assistant add-on install

1. Open the Home Assistant add-on store.
2. Add repository `https://github.com/GreenhillEfka/pilotsuite-styx-core` if needed.
3. Install **PilotSuite Core**.
4. Configure:
   - `log_level`
   - `ollama_host`
   - `ollama_port`
5. Start the add-on.

## First verification path

1. Confirm the add-on status is running.
2. Check `http://<home-assistant-host>:8909/health`.
3. Check `http://<home-assistant-host>:8909/version`.
4. Open the add-on UI and verify it loads.

## Next step

After Core is healthy, install PilotSuite HA from the separate HA repository.
