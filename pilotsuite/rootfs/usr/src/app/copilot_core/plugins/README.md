# Plugin List — PilotSuite Plugin System

**Version:** 7.10.0 (upcoming)  
**Structure:** `/copilot_core/plugins/`

---

## Core Plugins

| Plugin ID | Name | Description | Config Keys |
|-----------|------|-------------|-------------|
| `llm` | LLM Conversation | Local/cloud LLM conversations | `enabled`, `ollama_url`, `ollama_model`, `cloud_api_url`, `cloud_model`, `prefer_local`, `assistant_name`, `max_context_tokens` |
| `search` | SearXNG Search | Local privacy-respecting web search | `enabled`, `base_url`, `timeout`, `max_results`, `safesearch`, `default_language` |

---

## React Backend API (`/api/plugins`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/plugins` | GET | List all plugins with status |
| `/api/plugins/{id}/enable` | POST | Enable plugin |
| `/api/plugins/{id}/disable` | POST | Disable plugin |
| `/api/plugins/{id}/execute` | POST | Execute plugin with args |
| `/api/plugins/{id}/config` | PUT | Update plugin config |

---

## Configuration (config.yaml)

```yaml
plugins:
  llm:
    enabled: true
    ollama_url: "http://localhost:11435"
    ollama_model: "qwen3:0.6b"
    cloud_api_url: "https://ollama.com/v1"
    cloud_api_key: ""
    cloud_model: "gpt-oss:20b"
    prefer_local: true
    assistant_name: "Styx"
    max_context_tokens: 4096

  search:
    enabled: true
    base_url: "http://192.168.30.18:4041"
    timeout: 10
    max_results: 10
    safesearch: 0
    default_language: "auto"
```

---

## Plugin Developer Guide

Every plugin must:

1. Inherit from `PluginBase`
2. Define `PLUGIN_ID`, `PLUGIN_NAME`, `PLUGIN_VERSION`, `PLUGIN_DESCRIPTION`, `PLUGIN_CONFIG_SCHEMA`
3. Implement `execute(*args, **kwargs)`
4. Override `get_status()` for enhanced info

**Example:**

```python
from .plugin_base import PluginBase

class MyPlugin(PluginBase):
    PLUGIN_ID = "myplugin"
    PLUGIN_NAME = "My Plugin"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Does something cool"
    PLUGIN_CONFIG_SCHEMA = {"enabled": "bool", "my_setting": "str"}

    def execute(self, data: str) -> str:
        return f"Processed: {data}"
```

---

## Status

- ✅ `PluginBase` / `PluginManager` base classes
- ✅ `SearchPlugin` (SearXNG)
- ✅ `LLMPlugin` (Ollama/Cloud)
- ✅ `ReactBackendPlugin` (web UI API)
- ⏳ `llm_provider.py` integration (next step)
- ⏳ React UI toggle components (UI team)

**Groky Dev Check — Plugin System v1 ready for iteration. 🦝🔧🌙**
