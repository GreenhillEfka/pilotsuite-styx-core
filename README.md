# PilotSuite Core — Home Assistant Add-on

**Version:** 20.0.0  
**License:** MIT  
**Author:** GreenhillEfka

## Overview

PilotSuite Core is the brain of your AI-powered home. It provides semantic understanding, neural sensors, and intelligent automation logic.

## Architecture

```
┌─────────────────────────────────────┐
│  Home Assistant (HACS Integration)  │
│  - Entities, Sensors, Cards         │
│  - User Interface                   │
└──────────────┬──────────────────────┘
               │ HTTP API (Port 8909)
               ▼
┌─────────────────────────────────────┐
│  PilotSuite Core (This Add-on)      │
│  - Brain Architecture               │
│  - Neural Sensors                   │
│  - ML/AI Processing                 │
│  - API Server                       │
└─────────────────────────────────────┘
```

## Installation

### Via Add-on Store

1. Add repository: `https://github.com/GreenhillEfka/pilotsuite-styx-core`
2. Install "PilotSuite Core"
3. Configure (host, port, API keys)
4. Start the add-on

### Configuration

```yaml
log_level: info          # critical|error|warning|info|debug
ollama_host: localhost   # Ollama server host
ollama_port: 11434       # Ollama server port
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/version` | GET | Version info |
| `/api/v1/zones` | GET | Zone information |
| `/api/v1/presence` | GET | Presence status |
| `/api/v1/analytics` | GET | Analytics data |
| `/api/v1/notifications` | POST | Send notification |

Full API documentation: `docs/openapi.yaml`

## Features

- 🧠 **Brain Graph** — Neural representation of home state
- 🎯 **Presence Detection** — Multi-sensor fusion
- ⚡ **Energy Forecasting** — LSTM-based predictions
- 🗣️ **Voice Processing** — Local STT/TTS integration
- 📊 **Analytics Engine** — Insights & recommendations
- 🔔 **Notification System** — Smart alerting

## Requirements

- Home Assistant ≥ 2024.1.0
- Ollama server (optional, for local LLM)
- 2GB RAM minimum
- Docker support

## Support

- Issues: https://github.com/GreenhillEfka/pilotsuite-styx-core/issues
- Discord: PilotSuite Community
- Documentation: https://docs.pilotsuite.ai

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

**Built with ❤️ by the PilotSuite Team**
