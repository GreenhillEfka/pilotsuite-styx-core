"""Tests for Styx Agent Auto-Config (v5.21.0)."""

import time

import pytest

from copilot_core.agent_config import (
    AgentCapabilities,
    AgentGreeting,
    AgentStatus,
    _check_llm_available,
    _get_agent_version,
    _get_character,
    _get_features,
    _GREETINGS,
    init_agent_config,
)


@pytest.fixture
def config_default():
    """Standard config with Ollama."""
    return {
        "version": "5.21.0",
        "conversation": {
            "enabled": True,
            "ollama_url": "http://localhost:11434",
            "ollama_model": "qwen3:4b",
            "assistant_name": "Styx",
            "character": "copilot",
            "prefer_local": True,
            "cloud_api_url": "",
            "cloud_api_key": "",
            "cloud_model": "",
        },
        "openai_api": {"enabled": True},
        "brain_graph": {"max_nodes": 500},
        "knowledge_graph": {"enabled": True},
        "user_preferences": {"enabled": True},
        "telegram": {"enabled": False},
        "web_search": {"ags_code": "06412000"},
    }


@pytest.fixture
def config_cloud():
    """Config with cloud LLM."""
    return {
        "version": "5.21.0",
        "conversation": {
            "enabled": True,
            "prefer_local": False,
            "cloud_api_url": "https://api.example.com/v1",
            "cloud_model": "gpt-4",
            "assistant_name": "CloudStyx",
            "character": "butler",
        },
    }


@pytest.fixture
def config_minimal():
    """Minimal config with no extras."""
    return {
        "version": "5.21.0",
        "conversation": {
            "enabled": True,
            "prefer_local": True,
            "ollama_url": "http://localhost:11434",
            "ollama_model": "llama3",
        },
    }


# ── Test initialization ──────────────────────────────────────────────────


class TestInit:
    def test_init_default(self, config_default):
        init_agent_config(config=config_default)
        assert _get_agent_version() == "5.21.0"

    def test_init_none(self, monkeypatch):
        monkeypatch.delenv("COPILOT_VERSION", raising=False)
        monkeypatch.delenv("BUILD_VERSION", raising=False)
        init_agent_config(config=None)
        assert _get_agent_version() == "5.21.0"  # default

    def test_character(self, config_default):
        init_agent_config(config=config_default)
        assert _get_character() == "copilot"

    def test_character_butler(self, config_cloud):
        init_agent_config(config=config_cloud)
        assert _get_character() == "butler"


# ── Test LLM availability ───────────────────────────────────────────────


class TestLLMAvailability:
    def test_ollama_available(self, config_default):
        init_agent_config(config=config_default)
        available, model, backend = _check_llm_available()
        assert available is True
        assert model == "qwen3:4b"
        assert backend == "ollama"

    def test_cloud_available(self, config_cloud):
        init_agent_config(config=config_cloud)
        available, model, backend = _check_llm_available()
        assert available is True
        assert model == "gpt-4"
        assert backend == "cloud"

    def test_no_backend(self):
        init_agent_config(config={
            "conversation": {"prefer_local": False, "cloud_api_url": "", "cloud_model": ""},
        })
        available, model, backend = _check_llm_available()
        assert available is False
        assert backend == "none"

    def test_flat_options_keys_are_supported(self):
        init_agent_config(config={
            "conversation_prefer_local": True,
            "conversation_ollama_model": "qwen3:4b",
            "conversation_assistant_name": "Styx",
        })
        available, model, backend = _check_llm_available()
        assert available is True
        assert model == "qwen3:4b"
        assert backend == "ollama"


# ── Test features ────────────────────────────────────────────────────────


class TestFeatures:
    def test_default_features(self, config_default):
        init_agent_config(config=config_default)
        features = _get_features()
        assert "conversation" in features
        assert "chat_completions" in features
        assert "openai_compatible_api" in features
        assert "brain_graph" in features
        assert "knowledge_graph" in features
        assert "user_preferences" in features
        assert "regional_news" in features
        assert "regional_context" in features
        assert "energy_forecast" in features
        assert "proactive_alerts" in features

    def test_minimal_features(self, config_minimal):
        init_agent_config(config=config_minimal)
        features = _get_features()
        assert "conversation" in features
        assert "chat_completions" in features
        assert "regional_context" in features
        assert "telegram" not in features
        assert "regional_news" not in features

    def test_telegram_not_in_default(self, config_default):
        init_agent_config(config=config_default)
        features = _get_features()
        assert "telegram" not in features

    def test_telegram_enabled(self):
        init_agent_config(config={
            "version": "5.21.0",
            "conversation": {"enabled": True, "prefer_local": True, "ollama_model": "test"},
            "telegram": {"enabled": True},
        })
        features = _get_features()
        assert "telegram" in features


# ── Test dataclasses ─────────────────────────────────────────────────────


class TestDataclasses:
    def test_agent_status(self):
        status = AgentStatus(
            agent_name="Styx",
            agent_version="5.21.0",
            status="ready",
            uptime_seconds=120.0,
            conversation_ready=True,
            llm_available=True,
            llm_model="qwen3:4b",
            llm_backend="ollama",
            supported_languages=["de", "en"],
            character="copilot",
            features=["conversation"],
            last_health_check="2026-02-21T12:00:00",
        )
        assert status.status == "ready"
        assert status.agent_name == "Styx"

    def test_agent_capabilities(self):
        caps = AgentCapabilities(
            conversation=True,
            tool_calling=True,
            web_search=False,
            automation_creation=True,
            energy_management=True,
            mood_tracking=True,
            brain_graph=True,
            regional_context=True,
            proactive_alerts=True,
            multilingual=True,
            characters=["copilot", "butler"],
        )
        assert caps.conversation is True
        assert len(caps.characters) == 2

    def test_agent_greeting(self):
        greeting = AgentGreeting(
            language="de",
            greeting="Hallo!",
            introduction="Ich bin Styx.",
            capabilities_summary="Alles.",
            setup_hints=["Hint 1"],
        )
        assert greeting.language == "de"


# ── Test greetings ───────────────────────────────────────────────────────


class TestGreetings:
    def test_german_greeting(self):
        g = _GREETINGS["de"]
        assert g.language == "de"
        assert "Styx" in g.greeting
        assert len(g.setup_hints) >= 3

    def test_english_greeting(self):
        g = _GREETINGS["en"]
        assert g.language == "en"
        assert "Styx" in g.greeting
        assert len(g.setup_hints) >= 3

    def test_greeting_has_capabilities(self):
        for lang, g in _GREETINGS.items():
            assert len(g.capabilities_summary) > 20
            assert len(g.introduction) > 20
