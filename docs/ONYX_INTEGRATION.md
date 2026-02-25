# Onyx Integration Guide (PilotSuite Styx)

## Zielbild

Onyx und Styx haben getrennte Rollen:

- **Styx** steuert Home-Assistant-Aktionen, Habitus-Zonen und Runtime-Logik.
- **Onyx** liefert Chat-UX, Wissensbasis/RAG, Connectoren und Team-Workflows.

Damit bleibt Home-Automation stabil und Onyx kann als Wissens-/Agenten-Ebene wachsen.

## Produktiv-Konfig (Setup `192.168.30.18`)

### 1) LLM Provider in Onyx

- Provider Type: `OpenAI Compatible`
- Name: `Styx Local`
- Base URL: `http://192.168.30.18:8909/v1`
- API Key: dein Styx `auth_token` (Bearer)
- Default Model: `pilotsuite` (empfohlen) oder `qwen3:0.6b`

Hinweis: `pilotsuite` mappt intern auf das konfigurierte Styx/Ollama-Modell und ist update-stabil.

### 2) OpenAPI Action in Onyx

- Action Name: `Styx Home Actions`
- Schema: `docs/integrations/onyx_styx_actions.openapi.yaml`
- Auth Type: `Bearer`
- Bearer Token: derselbe Styx `auth_token`
- Server URL im Schema: `http://192.168.30.18:8909`

Wichtige Actions:
- `callHaServiceViaOnyxBridge` (`POST /api/v1/onyx/ha/service-call`) mit Rueckkanal (`readback_states`)
- `createZone` + `getZoneRooms` fuer Habitus-Zonen-Flow

### 3) MCP Server in Onyx (optional, empfohlen)

- Transport: `Streamable HTTP`
- URL: `http://192.168.30.18:8909/mcp`
- Header: `Authorization: Bearer <styx_auth_token>`
- Initial Test: JSON-RPC `initialize`

## E2E Smoke-Test

Mit einem Token pruefst du die komplette Kette:

```bash
TOKEN="<styx_auth_token>"
BASE="http://192.168.30.18:8909"

curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/onyx/status"
curl -sS -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/api/v1/onyx/ha/service-call" \
  -d '{"domain":"light","service":"turn_on","entity_id":"light.retrolampe","service_data":{"brightness_pct":45},"readback":true}'
curl -sS -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/mcp" -d '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{}}'
```

Wenn Onyx als Haupt-Chat dient, bleibt HA Assist trotzdem auf Styx sinnvoll (geringere Latenz, direkter HA-Kontext, robustere Aktionspfade).
