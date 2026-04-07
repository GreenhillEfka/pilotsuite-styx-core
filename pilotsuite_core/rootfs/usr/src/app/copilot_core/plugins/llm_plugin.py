"""
LLM Plugin for PilotSuite — LLM provider integration.

Provides conversation and inference via Ollama/Cloud LLMs.
"""

from typing import List, Dict, Any, Optional
from .plugin_base import PluginBase


class LLMPlugin(PluginBase):
    """LLM plugin — handles conversations and inference via Ollama/Cloud."""

    PLUGIN_ID = "llm"
    PLUGIN_NAME = "LLM Conversation"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "Local and cloud LLM conversations (Ollama, OpenAI-compatible)"
    PLUGIN_CONFIG_SCHEMA = {
        "enabled": "bool",
        "ollama_url": "str",
        "ollama_model": "str",
        "cloud_api_url": "str?",
        "cloud_api_key": "password?",
        "cloud_model": "str?",
        "prefer_local": "bool",
        "assistant_name": "str",
        "max_context_tokens": "int",
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.ollama_url = config.get("ollama_url", "http://localhost:11435")
        self.ollama_model = config.get("ollama_model", "qwen3:0.6b")
        self.cloud_api_url = config.get("cloud_api_url", "https://ollama.com/v1")
        self.cloud_api_key = config.get("cloud_api_key", "")
        self.cloud_model = config.get("cloud_model", "gpt-oss:20b")
        self.prefer_local = config.get("prefer_local", True)
        self.assistant_name = config.get("assistant_name", "Styx")
        self.max_context_tokens = config.get("max_context_tokens", 4096)

    def execute(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Execute LLM inference with optional tools."""
        if not self.enabled:
            return {"error": "LLM plugin disabled"}

        # Here you'd implement actual LLM API calls
        # Using Ollama or cloud API based on prefer_local
        return {
            "role": "assistant",
            "content": "LLM response placeholder",
            "model": self.ollama_model if self.prefer_local else self.cloud_model,
        }

    def get_status(self) -> Dict[str, Any]:
        """Return LLM plugin status."""
        status = super().get_status()
        status.update({
            "ollama_url": self.ollama_url,
            "ollama_model": self.ollama_model,
            "cloud_model": self.cloud_model,
            "prefer_local": self.prefer_local,
            "assistant_name": self.assistant_name,
        })
        return status
