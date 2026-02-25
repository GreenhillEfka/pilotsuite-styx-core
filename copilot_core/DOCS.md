# PilotSuite Core Add-on

## Exakte Installation

1. **Add-on installieren**: Add-on Store -> Menu (⋮) -> Repositories ->  
   `https://github.com/GreenhillEfka/pilotsuite-styx-core`
2. **PilotSuite Core starten** und auf `running` warten.
3. **HACS Integration installieren**:  
   `https://github.com/GreenhillEfka/pilotsuite-styx-ha`
4. **Integration hinzufügen**: Settings -> Devices & Services -> Add Integration -> **PilotSuite**.
5. **Dashboard-Wiring prüfen** (optional manuell):

```yaml
lovelace:
  dashboards:
    copilot-pilotsuite:
      mode: yaml
      title: "PilotSuite - Styx"
      icon: mdi:robot-outline
      show_in_sidebar: true
      filename: "pilotsuite-styx/pilotsuite_dashboard_latest.yaml"
    copilot-habitus-zones:
      mode: yaml
      title: "PilotSuite - Habitus Zones"
      icon: mdi:layers-outline
      show_in_sidebar: true
      filename: "pilotsuite-styx/habitus_zones_dashboard_latest.yaml"
```

## Konfiguration (wichtig)

| Option | Default | Zweck |
|---|---|---|
| `auth_token` | _(leer)_ | API-Token fuer Core + Dashboard |
| `conversation_ollama_url` | `http://localhost:11435` | lokaler Ollama-Endpunkt |
| `conversation_ollama_model` | `qwen3:0.6b` | Standardmodell (empfohlen) |
| `conversation_cloud_api_url` | _(leer)_ | externer Fallback (`https://ollama.com/v1`, OpenAI-kompatibel) |
| `conversation_cloud_api_key` | _(leer)_ | API-Key fuer externen Fallback |
| `conversation_cloud_model` | `gpt-4o-mini` | Cloud-Modell (wird fuer Ollama Cloud kompatibel gemappt) |
| `conversation_prefer_local` | `true` | lokal zuerst, dann Cloud-Fallback |

**Wo trage ich den Cloud API Key ein?**  
Im Add-on unter **Configuration** in `conversation_cloud_api_key`.

## Betriebs-Checks

- Core API: `GET /health`
- Chat-Status: `GET /chat/status`
- OpenAI-kompatibel: `POST /v1/chat/completions`
- Selbstreparatur: `POST /api/v1/agent/self-heal`

## Troubleshooting

- **LLM nicht erreichbar**: Add-on Logs prüfen, dann `/chat/status` aufrufen.
- **`model not found`**: lokales Modell (`qwen3:0.6b`) setzen oder Cloud-Fallback korrekt konfigurieren.
- **Dashboards fehlen**: Integration-Service `ai_home_copilot.show_installation_guide` ausführen und Anleitung übernehmen.
