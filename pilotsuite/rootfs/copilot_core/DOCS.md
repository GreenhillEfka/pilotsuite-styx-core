# PilotSuite Core Add-on

## Exakte Installation

1. **Add-on installieren**: Add-on Store -> Menu (⋮) -> Repositories ->
   `https://github.com/GreenhillEfka/pilotsuite-styx-core`
2. **PilotSuite Core starten** und auf `running` warten.
3. **HACS Integration installieren**:
   `https://github.com/GreenhillEfka/pilotsuite-styx-ha`
4. **Integration hinzufuegen**: Settings -> Devices & Services -> Add Integration -> **PilotSuite**.
5. **Dashboard-Wiring pruefen** (optional manuell):

```yaml
lovelace:
  dashboards:
    copilot-pilotsuite:
      mode: yaml
      title: "PilotSuite - Styx"
      icon: mdi:robot-outline
      show_in_sidebar: true
      filename: "pilotsuite-styx/pilotsuite_dashboard_latest.yaml"
```

## Konfiguration

| Option | Default | Zweck |
|---|---|---|
| `auth_token` | _(leer)_ | API-Token fuer Core + Dashboard |
| `conversation_ollama_url` | `http://localhost:11435` | lokaler Ollama-Endpunkt |
| `conversation_ollama_model` | `qwen3:0.6b` | Standardmodell (empfohlen) |
| `conversation_cloud_api_url` | _(leer)_ | externer Fallback (OpenAI-kompatibel) |
| `conversation_cloud_api_key` | _(leer)_ | API-Key fuer externen Fallback |
| `conversation_cloud_model` | `gpt-oss:20b` | Cloud-Modell |
| `conversation_prefer_local` | `true` | lokal zuerst, dann Cloud-Fallback |
| `conversation_assistant_name` | `Styx` | Name des KI-Assistenten |
| `conversation_enabled` | `true` | Chat-Funktion aktivieren/deaktivieren |
| `searxng_enabled` | `true` | SearXNG-Integration fuer Web-Suche |
| `searxng_base_url` | _(leer)_ | SearXNG-Server URL |
| `sonos_enabled` | `true` | Sonos-Steuerung via node-sonos-http-api |
| `sonos_port` | `5005` | Port fuer Sonos HTTP API |

## Module

| Modul | Beschreibung | Endpoints |
|---|---|---|
| **Brain Graph** | Neuronales Netzwerk mit Decay + Pruning | 15+ |
| **Mood Engine** | 6 diskrete Zustaende + 5 Dimensionen | 8 |
| **Habitus Zones** | Zone-Verwaltung + Entity-Mapping | 20+ |
| **Zone Automation** | Praesenz → Licht/Musik | 16 |
| **Sonos** | Sonos-Steuerung + Intelligenz | 37 |
| **Alarm/Wecker** | Smart-Wakeup + TTS-Durchsagen | 19 |
| **Conversation** | LLM-Chat + RAG-Pipeline | 10+ |
| **Error Digest** | Fehler-Analyse + Reparaturvorschlaege | 3 |
| **Suggestions** | KI-Vorschlaege mit Governance | 8 |
| **Media Zones** | Musikwolke + Follow-Mode | 12 |

**Gesamt: 596 API-Routen**

## Betriebs-Checks

| Endpunkt | Beschreibung |
|---|---|
| `GET /health` | Systemzustand + Uptime |
| `GET /version` | Installierte Version |
| `GET /chat/status` | LLM-Verbindungsstatus |
| `GET /api/v1/styx/dashboard` | Styx Dashboard (Web-UI) |
| `GET /api/v1/sonos/health` | Sonos-Service Status |
| `POST /api/v1/agent/self-heal` | Selbstreparatur-Agent |

## Troubleshooting

- **LLM nicht erreichbar**: Add-on Logs pruefen, dann `/chat/status` aufrufen.
- **`model not found`**: Lokales Modell (`qwen3:0.6b`) setzen oder Cloud-Fallback konfigurieren.
- **Sonos nicht erkannt**: `host_network: true` in config.yaml pruefen (noetig fuer UPnP/SSDP).
- **Dashboards fehlen**: Button "Dashboard generieren" im Haushalt-Tab druecken.
- **Fehler-Log leer**: Add-on neustarten, dann `/api/v1/errors/digest` pruefen.
