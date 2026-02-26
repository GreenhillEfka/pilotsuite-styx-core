# PilotSuite Core Add-on (Styx)

Stand: **v9.0.0**

## Installation (Production)

1. Home Assistant → **Einstellungen** → **Add-ons** → **Add-on Store**
2. Menü (⋮) → **Repositories**
3. Repository hinzufügen: `https://github.com/GreenhillEfka/pilotsuite-styx-core`
4. **PilotSuite Core** installieren und starten
5. Health prüfen: `http://<HA-IP>:8909/health`

## Passende HACS Integration

Zusätzlich installieren:
- `https://github.com/GreenhillEfka/pilotsuite-styx-ha`
- Integration: **PilotSuite - Styx**
- Verbindung zur Core API: Port `8909`

## Wichtige Konfigurationsfelder

| Option | Default | Zweck |
|---|---|---|
| `auth_token` | leer | Optionaler API-Schutz |
| `conversation_ollama_url` | `http://localhost:11435` | Lokaler Ollama-Endpunkt |
| `conversation_ollama_model` | `qwen3:0.6b` | Primäres Offline-Modell |
| `conversation_cloud_api_url` | `https://ollama.com/v1` | Cloud-Fallback-Endpunkt |
| `conversation_cloud_api_key` | leer | API-Key für Fallback |
| `conversation_cloud_model` | `qwen3.5:cloud` | Primäres Cloud-Modell |
| `conversation_prefer_local` | `true` | Lokal zuerst, Cloud nur Fallback |

## Betriebschecks

- `GET /health`
- `GET /chat/status`
- `GET /api/v1/status`
- `POST /v1/chat/completions`

## Troubleshooting

- `model not found`: lokales Modell pullen oder Cloud-Fallback korrekt setzen.
- `Kein LLM-Provider verfügbar`: `conversation_ollama_url` und/oder `conversation_cloud_*` prüfen.
- Nach HACS/Add-on Updates ist ein HA-Neustart oft erforderlich (`Restart required`).

## Hinweis

Die vollständige End-to-End-Setup-Anleitung (inkl. HA-Konfigflow) ist im HA-Repo unter `SETUP.md` dokumentiert.
